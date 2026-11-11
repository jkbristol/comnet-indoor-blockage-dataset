function RIS_Panel_Connect(RIS_Phases,t)

%%
%Pin mapping of RIS (Matrix to Serial data conversion)
c=mat2cell(RIS_Phases, [16 16 16 16], [64]); % Divid RIS panel into four Rows
r1= sprintf('%i', c{1,1}); % Separae strings of binary and convert to serial data
r2= sprintf('%i', c{2,1});
r3= sprintf('%i', c{3,1});
r4= sprintf('%i', c{4,1});
s = strcat(r1,r2,r3,r4); % Combine the serialize for for transfter
out=flip(s);

%% Send out stream to RIS

% Write data to the echo server.
% write(t,data)
% Confirm the success of the writing operation by viewing the NumBytesAvailable property.

write(t, out) %Send serial data to Raspi on TCP

%%
% Await acknowledgment

% reads all available numeric or ASCII data from the remote host specified by the TCP/IP client t and returns the data as a row or column vector of doubles or text.
% Using the read function with no arguments reads all available bytes of data from t connected to the remote host and returns the data
% Close the connection between the TCP/IP client and the remote host by clearing the object. Turn off the echotcpip server.
% clear t
% echotcpip("off")

rec = read(t); 

while(isempty(rec)) % determine whether array is empty 
    rec = read(t);
end
if rec == 97
    %fprintf('Send more \n')    
end
%%

end    
