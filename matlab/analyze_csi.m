% SECURESENSE-24: analysis of exported live CSI CSV (MATLAB R2021a+)
% Not used by the live program. FFT is temporal modulation, not 2.4 GHz RF.
% NOTE: time_monotonic_s is the PC receive time, including USB/OS jitter.
clear; clc; close all;
filename = 'securesense24_csi.csv';
assert(isfile(filename), 'Place an exported securesense24_csi.csv beside this script.');
T = readtable(filename, 'VariableNamingRule','preserve');
vars = string(T.Properties.VariableNames);
assert(ismember('rssi_dBm',vars), 'Expected exported rssi_dBm column.');
cols = startsWith(vars, 'subcarrier_') & endsWith(vars, '_amplitude');
assert(any(cols), 'No subcarrier amplitude columns in this CSV.');
A = double(T{:,cols});
A = A(:,any(isfinite(A),1));
assert(~isempty(A), 'No numeric CSI amplitudes found.');
meanA = mean(A,2,'omitnan');
rssi = double(T.rssi_dBm);
n = height(T);
figure('Name','SECURESENSE-24 CSI | Measured data');
subplot(3,1,1); plot(1:n,rssi); ylabel('RSSI (dBm)'); grid on;
title('Receiver RSSI over exported frames');
subplot(3,1,2); plot(1:n,meanA); ylabel('Mean |CSI| (a.u.)'); grid on;
title('Mean magnitude across available CSI bins');
% Like the dashboard, use a robust frame-to-frame change feature:
% median(abs(A_n-A_{n-1})) / max(1, median(A_{n-1})).
dA = abs(diff(A,1,1));
base = max(1,median(A(1:end-1,:),2,'omitnan'));
feature = median(dA,2,'omitnan') ./ base;
subplot(3,1,3); plot(2:n,feature); ylabel('Delta CSI (ratio)');
xlabel('Received CSI frame index'); grid on;
title('Robust inter-frame CSI variation');

if ~ismember('time_monotonic_s',vars)
    warning('No high-resolution time_monotonic_s column; skipping temporal FFT.');
    return;
end
t = double(T.time_monotonic_s);
t = t(2:end);
valid = isfinite(t) & isfinite(feature);
t = t(valid); feature = feature(valid);
[t,ia] = unique(t,'stable'); feature = feature(ia);
if numel(t) < 16 || any(diff(t)<=0)
    warning('Too few valid increasing timestamps for FFT.'); return;
end
% Irregular-arrival sampling -> interpolate to a uniform time grid.
dt = median(diff(t));
assert(dt > 0, 'Invalid timestamp interval');
fs = 1/dt;
tu = (t(1):dt:t(end)).';
if numel(tu) < 16, warning('Too short to compute useful FFT'); return; end
fu = interp1(t,feature,tu,'linear','extrap');
fu = fu-mean(fu,'omitnan');
N = numel(fu); k = (0:N-1).';
hannW = 0.5-0.5*cos(2*pi*k/(N-1));
Y = fft(fu.*hannW);
P = abs(Y(1:floor(N/2)+1));
f = (0:floor(N/2)).'*fs/N;
figure('Name','SECURESENSE-24 temporal spectrum');
plot(f,P); xlabel('Temporal frequency (Hz)');
ylabel('Uncalibrated FFT magnitude'); grid on;
title(sprintf('CSI change temporal FFT (resampled %.2f Hz)', fs));
% No RF center frequency / 2.4GHz spectrum conclusions from this FFT.
