/* SECURESENSE-24 v1.3 / ESP32-S3 / ESP-IDF 6.x
 * LD2410B radar on UART1 and 2.4-GHz router CSI on same MCU.
 * USB console emits newline-delimited SS24 JSON. Operates fully offline.
 * One reference assembly observed UART radar and live CSI telemetry.
 * Verify each new wiring, board revision and firmware build independently.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>
#include "driver/uart.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "lwip/ip4_addr.h"
#include "ping/ping_sock.h"
#include "esp_mac.h"
#include "ss24_wifi_config.h"


#define RADAR_UART UART_NUM_1
#define RADAR_TX 17
#define RADAR_RX 18
#define RADAR_BAUD 256000
#define FRAME_LEN 23
#define CSI_SUBCARRIERS 52

static const char *TAG = "SECURESENSE24";
static uint8_t frame[FRAME_LEN];
static size_t filled = 0;
static uint32_t radar_seq = 0;
static uint32_t csi_seq = 0;
static QueueHandle_t csi_queue = NULL;
static volatile int64_t last_csi_us = 0;
static bool gateway_ping_started = false;
static esp_ping_handle_t gateway_ping = NULL;
static uint8_t ap_bssid[6] = {0};
static volatile bool ap_bssid_ready = false;

typedef struct {
    int8_t rssi;
    uint8_t channel;
    unsigned count;
    uint16_t amp[CSI_SUBCARRIERS];
} csi_sample_t;

static bool valid_frame(const uint8_t *f) {
    static const uint8_t head[4] = {0xF4,0xF3,0xF2,0xF1};
    static const uint8_t tail[4] = {0xF8,0xF7,0xF6,0xF5};
    return memcmp(f,head,4)==0 && f[4]==0x0D && f[5]==0 &&
           f[6]==2 && f[7]==0xAA && f[8]<=3 && f[17]==0x55 &&
           f[18]==0 && memcmp(f+19,tail,4)==0;
}
static void emit_radar(const uint8_t *f){
    const unsigned state=f[8];
    const unsigned moving_cm=f[9] | ((unsigned)f[10]<<8);
    const unsigned still_cm=f[12] | ((unsigned)f[13]<<8);
    const unsigned detected_cm=f[15] | ((unsigned)f[16]<<8);
    const unsigned display_cm=detected_cm ? detected_cm : ((state&1) ? moving_cm : ((state&2) ? still_cm : 0));
    printf("SS24:{\"event\":\"radar\",\"seq\":%lu,\"state\":%u,\"presence\":%s,"
           "\"moving\":%s,\"stationary\":%s,\"moving_distance_cm\":%u,"
           "\"stationary_distance_cm\":%u,\"detection_distance_cm\":%u,"
           "\"display_distance_cm\":%u,\"moving_energy\":%u,\"stationary_energy\":%u}\n",
           (unsigned long)++radar_seq, state, state?"true":"false",
           (state&1)?"true":"false", (state&2)?"true":"false",
           moving_cm,still_cm,detected_cm,display_cm,f[11],f[14]);
    fflush(stdout);
}
static void accept_radar_byte(uint8_t b){
    if (filled < FRAME_LEN) frame[filled++]=b;
    if(filled != FRAME_LEN)return;
    if(valid_frame(frame)){emit_radar(frame);filled=0;}
    else{memmove(frame,frame+1,FRAME_LEN-1);filled=FRAME_LEN-1;}
}
static void radar_task(void *arg){
    const uart_config_t cfg={
        .baud_rate=RADAR_BAUD,.data_bits=UART_DATA_8_BITS,
        .parity=UART_PARITY_DISABLE,.stop_bits=UART_STOP_BITS_1,
        .flow_ctrl=UART_HW_FLOWCTRL_DISABLE,.source_clk=UART_SCLK_DEFAULT
    };
    ESP_ERROR_CHECK(uart_driver_install(RADAR_UART,4096,0,0,NULL,0));
    ESP_ERROR_CHECK(uart_param_config(RADAR_UART,&cfg));
    ESP_ERROR_CHECK(uart_set_pin(RADAR_UART,RADAR_TX,RADAR_RX,UART_PIN_NO_CHANGE,UART_PIN_NO_CHANGE));
    uint8_t bytes[256];
    while(true){
        int n=uart_read_bytes(RADAR_UART,bytes,sizeof(bytes),pdMS_TO_TICKS(250));
        for(int i=0;i<n;i++)accept_radar_byte(bytes[i]);
    }
}

/* Callback runs in Wi-Fi task. No printf/logging or expensive processing here. */
static void wifi_csi_cb(void *ctx, wifi_csi_info_t *info){
    if(!info || !info->buf || info->len < 4 || !csi_queue || !ap_bssid_ready)return;
    /* Keep only CSI frames transmitted by the associated router/AP. */
    if (memcmp(info->mac, ap_bssid, sizeof(ap_bssid)) != 0) return;
    const int64_t now=esp_timer_get_time();
    if(now-last_csi_us < 125000)return; /* bound console to <=8 CSI samples/s */
    last_csi_us=now;
    csi_sample_t item={0};
    item.rssi=info->rx_ctrl.rssi;
    item.channel=info->rx_ctrl.channel;
    /* CSI IQ pair is [imag, real]. Magnitude is derived from signed IQ. */
    unsigned pairs=info->len/2;
    item.count=(pairs<CSI_SUBCARRIERS)?pairs:CSI_SUBCARRIERS;
    unsigned start=info->first_word_invalid && pairs>2 ? 2 : 0;
    if(item.count==0)return;
    for(unsigned i=0;i<item.count;i++){
        unsigned p=start + (i*(pairs-start))/item.count;
        if(p>=pairs)p=pairs-1;
        float imag=(float)info->buf[2*p];
        float real=(float)info->buf[2*p+1];
        item.amp[i]=(uint16_t)sqrtf(real*real+imag*imag);
    }
    xQueueSend(csi_queue,&item,0);
}
static void csi_output_task(void *arg){
    csi_sample_t item;
    while(true){
        if(xQueueReceive(csi_queue,&item,portMAX_DELAY)!=pdTRUE)continue;
        char line[768];
        int n=snprintf(line,sizeof(line),
                "SS24:{\"event\":\"csi\",\"seq\":%lu,\"rssi\":%d,\"channel\":%u,\"subcarrier_amplitude\":[",
                (unsigned long)++csi_seq,item.rssi,item.channel);
        if(n<0 || n>=(int)sizeof(line)) continue;
        size_t offset=(size_t)n;
        for(unsigned i=0;i<item.count;i++){
            n=snprintf(line+offset,sizeof(line)-offset,"%s%u",i?",":"",item.amp[i]);
            if(n<0 || (size_t)n>=sizeof(line)-offset)break;
            offset+=(size_t)n;
        }
        if(offset+4<sizeof(line)){
            memcpy(line+offset,"]}\n",4);
            line[offset+3]='\0';
            fputs(line,stdout);
            fflush(stdout);
        }
    }
}
static void start_gateway_ping(const esp_netif_ip_info_t *ip) {
    if (gateway_ping_started) return;
    if (ip->gw.addr == 0) {
        ESP_LOGW(TAG, "Router does not advertise a gateway; no automatic ICMP excitation");
        return;
    }
    esp_ping_config_t cfg = ESP_PING_DEFAULT_CONFIG();
    cfg.count = 0;                    /* unlimited pings while connected */
    cfg.interval_ms = 120;           /* ~8.3 Hz CSI stimulus, no Internet */
    cfg.timeout_ms = 750;
    cfg.data_size = 16;
    cfg.target_addr.u_addr.ip4.addr = ip4_addr_get_u32(&ip->gw);
    cfg.target_addr.type = ESP_IPADDR_TYPE_V4;
    esp_ping_callbacks_t callbacks = {0};
    esp_err_t err = esp_ping_new_session(&cfg, &callbacks, &gateway_ping);
    if (err == ESP_OK) {
        err = esp_ping_start(gateway_ping);
        if (err == ESP_OK) {
            gateway_ping_started = true;
            ESP_LOGI(TAG, "Automatic local ICMP echo to router started (120 ms interval)");
        }
    }
    if (err != ESP_OK) ESP_LOGE(TAG, "Gateway Ping failed: %s", esp_err_to_name(err));
}

static void wifi_events(void *ctx, esp_event_base_t base, int32_t id, void *event){
    if(base == WIFI_EVENT && id == WIFI_EVENT_STA_START){
        esp_wifi_connect();
    } else if(base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED){
        ap_bssid_ready = false;
        if (gateway_ping_started && gateway_ping != NULL) {
            esp_ping_stop(gateway_ping);
            gateway_ping_started = false;
        }
        printf("SS24:{\"event\":\"wifi\",\"connected\":false}\n");
        ESP_LOGW(TAG,"Wi-Fi disconnected; retrying local router");
        esp_wifi_connect();
    } else if(base == IP_EVENT && id == IP_EVENT_STA_GOT_IP){
        ip_event_got_ip_t *ev=(ip_event_got_ip_t*)event;
        wifi_ap_record_t ap = {0};
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            memcpy(ap_bssid, ap.bssid, sizeof(ap_bssid));
            ap_bssid_ready = true;
        }
        ESP_LOGI(TAG,"Wi-Fi connected; ESP32 IP: " IPSTR,IP2STR(&ev->ip_info.ip));
        printf("SS24:{\"event\":\"wifi\",\"connected\":true,\"ip\":\"" IPSTR "\",\"channel\":%u,\"rssi\":%d}\n",
               IP2STR(&ev->ip_info.ip), ap.primary, ap.rssi);
        fflush(stdout);
        if (gateway_ping != NULL) {
            esp_ping_start(gateway_ping);
            gateway_ping_started = true;
        } else start_gateway_ping(&ev->ip_info);
    }
}
static void wifi_csi_start(void){
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t init_cfg=WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,&wifi_events,NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,&wifi_events,NULL));
    wifi_config_t cfg={0};
    strlcpy((char*)cfg.sta.ssid,SS24_WIFI_SSID,sizeof(cfg.sta.ssid));
    strlcpy((char*)cfg.sta.password,SS24_WIFI_PASSWORD,sizeof(cfg.sta.password));
    cfg.sta.threshold.authmode=WIFI_AUTH_WPA2_PSK;
    cfg.sta.pmf_cfg.capable = true;
    cfg.sta.pmf_cfg.required = false;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA,&cfg));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    const wifi_csi_config_t csi={
        .lltf_en=true,.htltf_en=true,.stbc_htltf2_en=true,
        .ltf_merge_en=true,.channel_filter_en=false,
        .manu_scale=false,.shift=0,.dump_ack_en=false
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(wifi_csi_cb,NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));
    ESP_LOGI(TAG,"CSI capture armed; waiting for router packets");
}
static void wifi_status_task(void *arg){
    while(true){
        vTaskDelay(pdMS_TO_TICKS(5000));
        if(!ap_bssid_ready) continue;
        esp_netif_t *iface=esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
        esp_netif_ip_info_t ip={0};
        wifi_ap_record_t ap={0};
        if(iface && esp_netif_get_ip_info(iface,&ip)==ESP_OK &&
           esp_wifi_sta_get_ap_info(&ap)==ESP_OK) {
            printf("SS24:{\"event\":\"wifi\",\"connected\":true,\"ip\":\"" IPSTR "\",\"channel\":%u,\"rssi\":%d}\n",
                   IP2STR(&ip.ip), ap.primary, ap.rssi);
            fflush(stdout);
        }
    }
}
void app_main(void){
    ESP_LOGI(TAG,"SECURESENSE-24 v1.3 / RADAR + OFFLINE ROUTER CSI");
    esp_err_t err=nvs_flash_init();
    if(err==ESP_ERR_NVS_NO_FREE_PAGES || err==ESP_ERR_NVS_NEW_VERSION_FOUND){
        ESP_ERROR_CHECK(nvs_flash_erase());
        err=nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    csi_queue=xQueueCreate(8,sizeof(csi_sample_t));
    if(!csi_queue){ESP_LOGE(TAG,"CSI queue allocation failed");return;}
    xTaskCreate(radar_task,"ss24_radar",4096,NULL,5,NULL);
    xTaskCreate(csi_output_task,"ss24_csi",4096,NULL,4,NULL);
    xTaskCreate(wifi_status_task,"ss24_wifi_stat",3072,NULL,3,NULL);
    wifi_csi_start();
}
