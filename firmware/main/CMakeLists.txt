idf_component_register(
    SRCS "hello_world_main.c"
    INCLUDE_DIRS "."
    REQUIRES esp_driver_uart esp_wifi esp_event esp_netif nvs_flash esp_timer lwip
)
