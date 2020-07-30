#---------------------------------------
#   Import Libraries
#---------------------------------------
import logging
from logging.handlers import TimedRotatingFileHandler
import clr
import re
import os
import codecs
import json
import uuid
from collections import deque
clr.AddReference("SocketIOClientDotNet.dll")
clr.AddReference("Newtonsoft.Json.dll")
from System import Uri, Action
from Quobject.SocketIoClientDotNet import Client as SocketIO
from Newtonsoft.Json.JsonConvert import SerializeObject as JSONDump

#---------------------------------------
#   [Required] Script Information
#---------------------------------------
ScriptName = 'StreamlabsSocketMirror'
Website = 'https://github.com/nossebro/StreamlabsSocketMirror'
Creator = 'nossebro'
Version = '0.0.1'
Description = 'Mirrors events from the Streamlabs socket, and sends them to the local SLCB socket'

#---------------------------------------
#   Script Variables
#---------------------------------------
ScriptSettings = None
StreamlabsSocketAPI = None
UserIDCache = None
Logger = None
SettingsFile = os.path.join(os.path.dirname(__file__), "Settings.json")
UIConfigFile = os.path.join(os.path.dirname(__file__), "UI_Config.json")

#---------------------------------------
#   Script Classes
#---------------------------------------
class StreamlabsLogHandler(logging.StreamHandler):
	def emit(self, record):
		try:
			message = self.format(record)
			Parent.Log(ScriptName, message)
			self.flush()
		except (KeyboardInterrupt, SystemExit):
			raise
		except:
			self.handleError(record)

class Settings(object):
	def __init__(self, settingsfile=None):
		defaults = self.DefaultSettings(UIConfigFile)
		try:
			with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
				settings = json.load(f, encoding="utf-8")
			self.__dict__ = MergeLists(defaults, settings)
		except:
			self.__dict__ = defaults

	def DefaultSettings(self, settingsfile=None):
		defaults = dict()
		with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
			ui = json.load(f, encoding="utf-8")
		for key in ui:
			try:
				defaults[key] = ui[key]['value']
			except:
				if key != "output_file":
					Parent.Log(ScriptName, "DefaultSettings(): Could not find key {0} in settings".format(key))
		return defaults

	def Reload(self, jsondata):
		self.__dict__ = MergeLists(self.DefaultSettings(UIConfigFile), json.loads(jsondata, encoding="utf-8"))

#---------------------------------------
#   Script Functions
#---------------------------------------
def GetLogger():
	log = logging.getLogger(ScriptName)
	log.setLevel(logging.DEBUG)

	sl = StreamlabsLogHandler()
	sl.setFormatter(logging.Formatter("%(funcName)s(): %(message)s"))
	sl.setLevel(logging.INFO)
	log.addHandler(sl)

	fl = TimedRotatingFileHandler(filename=os.path.join(os.path.dirname(__file__), "info"), when="w0", backupCount=8, encoding="utf-8")
	fl.suffix = "%Y%m%d"
	fl.setFormatter(logging.Formatter("%(asctime)s  %(funcName)s(): %(levelname)s: %(message)s"))
	fl.setLevel(logging.INFO)
	log.addHandler(fl)

	if ScriptSettings.DebugMode:
		dfl = TimedRotatingFileHandler(filename=os.path.join(os.path.dirname(__file__), "debug"), when="h", backupCount=24, encoding="utf-8")
		dfl.suffix = "%Y%m%d%H%M%S"
		dfl.setFormatter(logging.Formatter("%(asctime)s  %(funcName)s(): %(levelname)s: %(message)s"))
		dfl.setLevel(logging.DEBUG)
		log.addHandler(dfl)

	log.debug("Logger initialized")
	return log

def MergeLists(x = dict(), y = dict()):
	for attr in x:
		if attr not in y:
			y.append(attr)
	return y

def Nonce():
	nonce = uuid.uuid1()
	oauth_nonce = nonce.hex
	return oauth_nonce

def GetTwitchUserID(Username = None):
	global ScriptSettings
	global Logger
	ID = None
	if not Username:
		Username = ScriptSettings.StreamerName
	Header = {
		"Client-ID": ScriptSettings.JTVClientID,
		"Authorization": "Bearer {0}".format(ScriptSettings.JTVToken)
	}
	Logger.debug("Header: {0}".format(json.dumps(Header)))
	result = json.loads(Parent.GetRequest("https://api.twitch.tv/helix/users?login={0}".format(Username.lower()), Header))
	if result["status"] == 200:
		response = json.loads(result["response"])
		Logger.debug("Response: {0}".format(json.dumps(response)))
		ID = response["data"][0]["id"]
		Logger.debug("ID: {0}".format(ID))
	elif "error" in result:
		Logger.error("Error Code {0}: {1}".format(result["status"], result["error"]))
	else:
		Logger.warning("Response unknown: {0}".format(result))
	return ID

#---------------------------------------
#   Chatbot Initialize Function
#---------------------------------------
def Init():
	global ScriptSettings
	ScriptSettings = Settings(SettingsFile)
	global Logger
	Logger = GetLogger()
	Parent.BroadcastWsEvent('{0}_UPDATE_SETTINGS'.format(ScriptName.upper()), json.dumps(ScriptSettings.__dict__))
	Logger.debug(json.dumps(ScriptSettings.__dict__), True)

	global StreamlabsSocketAPI
	url = Uri("https://sockets.streamlabs.com")
	options = SocketIO.IO.Options(AutoConnect=False, QueryString="token={0}".format(ScriptSettings.SLSocketToken))
	StreamlabsSocketAPI = SocketIO.IO.Socket(url, options)
	StreamlabsSocketAPI.On("event", Action[object](StreamlabsSocketAPIEvent))
	StreamlabsSocketAPI.On(SocketIO.Socket.EVENT_CONNECT, Action[object](StreamlabsSocketAPIConnected))
	StreamlabsSocketAPI.On(SocketIO.Socket.EVENT_CONNECT_ERROR, Action[object](StreamlabsSocketAPIError))
	StreamlabsSocketAPI.On(SocketIO.Socket.EVENT_CONNECT_TIMEOUT, Action[object](StreamlabsSocketAPIError))
	StreamlabsSocketAPI.On(SocketIO.Socket.EVENT_DISCONNECT, Action[object](StreamlabsSocketAPIDisconnected))
	StreamlabsSocketAPI.On(SocketIO.Socket.EVENT_ERROR, Action[object](StreamlabsSocketAPIError))
	StreamlabsSocketAPI.On(SocketIO.Socket.EVENT_MESSAGE, Action[object](StreamlabsSocketAPIMessage))
	StreamlabsSocketAPI.On(SocketIO.Socket.EVENT_RECONNECT_ERROR, Action[object](StreamlabsSocketAPIError))
	StreamlabsSocketAPI.On(SocketIO.Socket.EVENT_RECONNECT_FAILED, Action[object](StreamlabsSocketAPIError))

	if ScriptSettings.SLSocketToken:
		StreamlabsSocketAPI.Connect()
	else:
		Logger.warning("Streamlabs Socket Token not configured")

	global UserIDCache
	UserIDCache = deque(list(), 100)

#---------------------------------------
#   Chatbot Script Unload Function
#---------------------------------------
def Unload():
	global StreamlabsSocketAPI
	global Logger
	if StreamlabsSocketAPI:
		StreamlabsSocketAPI.Close()
		StreamlabsSocketAPI = None
		Logger.debug("StreamlabsSocketAPI Disconnected")
	if Logger:
		Logger.handlers.Clear()
		Logger = None

#---------------------------------------
#   Chatbot Save Settings Function
#---------------------------------------
def ReloadSettings(jsondata):
	ScriptSettings.Reload(jsondata)
	Logger.debug("Settings reloaded")
	Parent.BroadcastWsEvent('{0}_UPDATE_SETTINGS'.format(ScriptName.upper()), json.dumps(ScriptSettings.__dict__))
	Logger.debug(json.dumps(ScriptSettings.__dict__), True)

#---------------------------------------
#   Chatbot Execute Function
#---------------------------------------
def Execute(data):
	pass

#---------------------------------------
#   Chatbot Tick Function
#---------------------------------------
def Tick():
	pass

#---------------------------------------
#   StreamlabsSocketAPI Connect Function
#---------------------------------------
def StreamlabsSocketAPIConnected(data):
	Logger.debug("Connected")

#---------------------------------------
#   StreamlabsSocketAPI Disconnect Function
#---------------------------------------
def StreamlabsSocketAPIDisconnected(data):
	global Logger
	Logger.debug("Disconnected: {0}".format(data))

#---------------------------------------
#   StreamlabsSocketAPI Error Function
#---------------------------------------
def StreamlabsSocketAPIError(data):
	global Logger
	Logger.error(data.Message)
	Logger.exception(data)

#---------------------------------------
#   StreamlabsSocketAPI Message Function
#---------------------------------------
def StreamlabsSocketAPIMessage(data):
	Logger.info("Message: {0}".format(json.dumps(json.loads(JSONDump(data)))))

#---------------------------------------
#   StreamlabsSocketAPI Event Function
#---------------------------------------
def StreamlabsSocketAPIEvent(data):
	event = json.loads(JSONDump(data))
	if ScriptSettings.MirrorAll:
		Logger.debug("Send original event to Local Socket")
		Parent.BroadcastWsEvent("STREAMLABS", json.dumps(event))
	if not "message" in event:
		Logger.debug("No message in event: {0}".format(json.dumps(event)))
		return
	if not "for" in event:
		Logger.debug("No for in event: {0}".format(json.dumps(event)))
		event["for"] = "streamlabs"
	if isinstance(event["message"], dict):
		event["message"] = json.loads( "[ {0} ]".format(json.dumps(event["message"])))
	for message in event["message"]:
		if "isTest" in message:
			if not ScriptSettings.SLTestMode:
				Logger.warning("Received test event, resend disabled in configuration")
				Logger.debug(json.dumps(event))
				continue
		if "repeat" in message:
			if not ScriptSettings.SLRepeat:
				Logger.warning("Received repeated event, resend disabled in configuration")
				Logger.debug(json.dumps(event))
				continue
		if event["for"] == "streamlabs":
			if event["type"] == "donation":
				Logger.info(message)
			elif event["type"] == "loyalty_store_redemption":
				Logger.info(message)
			elif event["type"] == "merch":
				Logger.info(message)
			elif event["type"] == "prime_sub_gift":
				Logger.info(message)
			else:
				Logger.warning("Unrecognised event for {0}: {1}".format(event["for"], json.dumps(event)))
				pass
		elif event["for"] == "twitch_account":
			if event["type"] == "bits":
				Logger.info(message)
			elif event["type"] == "follow":
				Logger.info(message)
			elif event["type"] == "host":
				Logger.info(message)
			elif event["type"] == "raid":
				Logger.info(message)
			elif event["type"] == "subscription":
				Logger.info(message)
			elif event["type"] == "resub":
				Logger.info(message)
			else:
				Logger.warning("Unrecognised event for {0}: {1}".format(event["for"], json.dumps(event)))
				pass
		else:
			Logger.warning("Unrecognised event for {0}: {1}".format(event["for"], json.dumps(event)))
