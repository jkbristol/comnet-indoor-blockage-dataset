% SNR Calculations 
 close all;
   clear;
rx = comm.SDRuReceiver(...
    'Platform', 'X310', ... 
    'IPAddress', '192.168.10.2', ...
    'CenterFrequency', 3.58e9, ...
    'Gain', 30, ... 
    'MasterClockRate', 184.32e6, ...
    'DecimationFactor', 16, ...
    'OutputDataType', 'double', ...
    'SampleRate', 11.52e6, ...
    'EnableBurstMode', true, ...
    'NumFramesInBurst', 10, ...
    'SamplesPerFrame', 4096);

% Prepare for data logging
logFile = fopen('rx_data.bin', 'wb');
snrLogFile = fopen('snr_log.txt', 'w');
numFrames = 1000;
snrValues = zeros(1, numFrames);

% Stream received data and calculate SNR
disp('Receiving data...');
for i = 1:numFrames
    data = rx(); % Receive signal
    if isempty(data)
        disp('No data received. Check USRP settings.');
        break;
    end
    
    fwrite(logFile, data, 'double'); % Save received samples

    % SNR Calculation
    signalPower = mean(abs(data).^2); % Power of the received signal
    noisePower = var(data); % Assuming noise is variance of signal
    snr = 10 * log10(signalPower / noisePower); % SNR in dB
    snrValues(i) = snr;

    fprintf(snrLogFile, 'Frame %d: SNR = %.2f dB\n', i, snr);
end

fclose(logFile);
fclose(snrLogFile);
release(rx);
disp('Data reception complete. SNR calculation done.');

% Plot SNR over time
figure;
plot(1:numFrames, snrValues, '-o');
xlabel('Frame Number');
ylabel('SNR (dB)');
title('SNR over Time');
grid on;
