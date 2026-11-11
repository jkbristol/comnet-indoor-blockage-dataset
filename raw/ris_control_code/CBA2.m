close all;
clear;
clc;
%% Define parameters
M = 64; % Rows of the RIS matrix
N = 64; % Columns of the RIS matrix
L = 4096; % Number of configurations
numConfigurations = L;

%% Create the Hadamard 4096x4096 matrix
code_beamforming = hadamard(M * N);

% Quantize the Hadamard matrix to contain only 0s and 1s
code_beamforming(code_beamforming == -1) = 0;

%% Convert each column in code_beamforming into a 64x64 Matrix
Matrix64x64 = zeros(64, 64, L); % Initialize with zeros
for s = 1:L
    Matrix64x64(:, :, s) = reshape(code_beamforming(:, s), [M, N]);
end

%% Setup SDR Receiver
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
    'NumFramesInBurst', 5, ... % Increased number of frames for better averaging
    'SamplesPerFrame', 1024);

%% Establish connection to RIS
t = tcpclient("192.168.5.1", 9090);

%% SNR Measurement Loop
SNR_values = zeros(1, numConfigurations);

for config = 3:7
    % Load and send RIS configuration
    B = Matrix64x64(:, :, config);
    RIS_Panel_Connect(B, t);
    
    pause(20); % Allow RIS and receiver to stabilize

    % Receive multiple frames and compute average SNRRIS_Panel_Connect(B, t);
    receivedData = zeros(rx.SamplesPerFrame, rx.NumFramesInBurst);
    for frameIdx = 1:rx.NumFramesInBurst
        receivedData(:, frameIdx) = rx();
    end
    avgData = mean(receivedData, 2); % Averaging over frames

    % Compute SNR
    signalPower = mean(abs(avgData).^2);
    noisePower = var(avgData);
    SNR_values(config) = 10 * log10(signalPower / noisePower);

    fprintf('Config %d: SNR = %.2f dB\n', config, SNR_values(config));
end

%% Find configurations with max and min SNR
[maxSNR, maxIdx] = max(SNR_values);
[minSNR, minIdx] = min(SNR_values);

bestConfig = Matrix64x64(:, :, maxIdx);
worstConfig = Matrix64x64(:, :, minIdx);

fprintf('Max SNR = %.2f dB at Config %d\n', maxSNR, maxIdx);
fprintf('Min SNR = %.2f dB at Config %d\n', minSNR, minIdx);

%% Save the best and worst configurations
save('best_worst_config.mat', 'bestConfig', 'worstConfig', 'maxSNR', 'minSNR', 'maxIdx', 'minIdx');

%% Plot SNR values
figure;
plot(1:numConfigurations, SNR_values, 'b', 'LineWidth', 1.5); hold on;
scatter(maxIdx, maxSNR, 100, 'r', 'filled'); % Mark max SNR
scatter(minIdx, minSNR, 100, 'g', 'filled'); % Mark min SNR
xlabel('RIS Configuration Index');
ylabel('SNR (dB)');
title('SNR vs. RIS Configurations');
legend('SNR Values', 'Max SNR', 'Min SNR');
grid on;

figure;
surfPlot = surf(1:M, 1:N, bestConfig, 'EdgeColor', 'none'); % Initialize the surf plot
colormap(parula); % Set colormap
colorbar; % Add colorbar
view(2); % Set to top-down 2D view
xlabel('Horizontal element index', 'Interpreter', 'latex'); % Label for x-axis
ylabel('Vertical element index', 'Interpreter', 'latex'); % Label for y-axis
title('Real-Time Hadamard best Configuration', 'Interpreter', 'latex'); % Title
set(gca, 'fontsize', 18); % Set font size
xlim([1 M]); % Set x-axis limits
ylim([1 N]); % Set y-axis limits

figure;
surfPlot = surf(1:M, 1:N, worstConfig, 'EdgeColor', 'none'); % Initialize the surf plot
colormap(parula); % Set colormap
colorbar; % Add colorbar
view(2); % Set to top-down 2D view
xlabel('Horizontal element index', 'Interpreter', 'latex'); % Label for x-axis
ylabel('Vertical element index', 'Interpreter', 'latex'); % Label for y-axis
title('Real-Time Hadamard worst Configuration', 'Interpreter', 'latex'); % Title
set(gca, 'fontsize', 18); % Set font size
xlim([1 M]); % Set x-axis limits
ylim([1 N]); % Set y-axis limits

hold off;
