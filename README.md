# StreamlabsSocketMirror

A Streamlabs Chatbot (SLCB) Script that uses [SocketIOClientDotNet](https://github.com/Quobject/SocketIoClientDotNet) and [Newtonsoft](https://www.newtonsoft.com/json) to mirror events from Streamlabs API socket, and sends them to the local SLCB socket

For a local event listner, you can install [SocketReceiver](https://github.com/nossebro/SocketReceiver), and subscribe to the `STREAMLABS` event.

Script could also be used as a stand alone template, modifying `StreamlabsSocketAPIEvent` logic for Socket.IO events.

## Installation

1. Login to Streamlabs and go to <https://streamlabs.com/dashboard#/settings/api-settings>, noting the Socket Token under the API Token tab.
2. Install the script in SLCB. (Please make sure you have configured the correct [32-bit Python 2.7.13](https://www.python.org/ftp/python/2.7.13/python-2.7.13.msi) Lib-directory).
3. Review the script's configuration in SLCB, providing the Socket Token from step 1.

## Thank-you's

This work is heavily based on the [Streamlabs-Events-Receiver](https://github.com/ocgineer/Streamlabs-Events-Receiver) by [ocgineer](https://github.com/ocgineer)
