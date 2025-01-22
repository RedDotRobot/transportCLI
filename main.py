import requests
from dotenv import load_dotenv
import os
import collections.abc
import cmd2
import datetime
import time
import logging
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.completion import WordCompleter
import json
import sys

collections.Callable = collections.abc.Callable

class ColourFormatter(logging.Formatter):
	colours = {
		"DEBUG": "\033[92m",
		"INFO": "\033[94m",
		"WARNING": "\033[93m",
		"ERROR": "\033[91m",
		"CRITICAL": "\033[95m"
	}
	RESET = "\033[0m"

	# Assign colour
	def format(self, record):
		logColour = self.colours.get(record.levelname, self.RESET)
		record.levelname = f"{logColour}{record.levelname}{self.RESET}"
		if record.levelname == "[92mDEBUG[0m":	# Makes debug msgs black
			record.msg = f"\033[0;30m{record.msg}{self.RESET}"
		return super().format(record)

logger = logging.getLogger("customlogger")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()  # Output to console
console_handler.setLevel(logging.DEBUG)
formatter = ColourFormatter(
	"%(asctime)s > %(levelname)s > %(message)s"
)

# Assign the formatter to the handler
console_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(console_handler)

load_dotenv()
apiKey = os.getenv("API_KEY")
apiEndpoint = "https://api.transport.nsw.gov.au/v1/tp/"
headers = {
	"Authorization": f"apikey {apiKey}"
}

class httpsStatusCodeSwitch:
	def OK(self, message):
		logger.debug(f"Response successful")

	def limitReached(self, message):
		logger.warning(f"Quota/Rate limit reached: {message}")

	def movedPermanently(self, message):
		logger.critical(f"URI has changed: {message}")

	def badRequest(self, message):
		logger.error(f"Bad request: {message}")

	def unauthorized(self, message):
		logger.error(f"Unauthorised request: {message}")

	def default(self):
		logger.error(f"Invalid HTTPS code")

	def switchCase(self, code, message):
		switch = {
			200: self.OK,
			203: self.limitReached,
			301: self.movedPermanently,
			400: self.badRequest,
			401: self.unauthorized
		}
		handler = switch.get(code, self.default)
		handler(message)

def getData(url, params, headers):
	httpsStatus = httpsStatusCodeSwitch()
	response = requests.get(url, params=params, headers=headers)
	responseStatusCode = response.status_code
	responseData = response.json()
	with open(f"responses/{time.time()}.json", "w") as file:
		json.dump(responseData, file, indent=4)
	if responseStatusCode != 200:
		message = responseData["ErrorDetails"]["Message"]
	else:
		message = ""
	httpsStatus.switchCase(responseStatusCode, message)
	return responseData

class transportCLI(cmd2.Cmd):
	def __init__(self, completekey = "tab", stdin = None, stdout = None):
		super().__init__(completekey, stdin, stdout)
		self.prompt = ">> "
		self.intro = "Welcome to transportCLI. Type \"help\" for available commands."

	def do_quit(self, line):
		self.exit_code = 2

	def do_test(self, line):
		"""Print a greeting."""
		print("Hello, World!")


	def do_menuchange(self, line):
		print("changed to menu 1")

	def do_quit(self, line):
		"""Exit the CLI."""
		return True
	
	def do_stopfinder(self, line):
		url = f"{apiEndpoint}stop_finder"
		params = {
			"outputFormat": "rapidJSON",
			"type_sf": "any",
			"name_sf": "Circular Quay",
			"coordOutputFormat": "EPSG:4326",
			"anyMaxSizeHitList": 10
		}
		data = getData(url, params, headers)
		print(data)
	
	def do_alert(self, arg:str):
		url = f"{apiEndpoint}add_info"
		date = datetime.date.today().strftime("%d-%m-%Y")
		params = {
			"outputFormat": "rapidJSON",
			"coordOutputFormat": "EPSG:4326",
			"filterDateValid": date,
			"filterPublicationStatus": "current"
		}
		data = getData(url, params, headers)
		print(arg)
		infos = data.get("infos")
		currentInfos = infos.get("current")
		for message in currentInfos:
			printList =[]
			heading = message.get("subtitle")
			url = message.get("url")
			properties = message.get("properties")
			speechText = properties.get("speechText")
			affected = message.get("affected", {})
			lines = affected.get("lines", [])
			stops = affected.get("stops", [])
			if arg in ["bus"]:
				for ln in lines:
					operator = ln.get("operator")
					if heading not in printList and operator.get("name") in ["Transit Systems NSW", "Busways R1"]:
						print(heading)
						print(speechText)
						print(f"Affected Lines: {len(lines)}")
						print(f"Affected Stops: {len(stops)}")
						printList.append(heading)
			elif arg in ["train", ""]:
				for ln in lines:
					operator = ln.get("operator")
					if heading not in printList and operator.get("name") in ["Sydney Trains", "NSW TrainLink Train"]:
						print
						print(heading)
						print(speechText)
						print(f"Affected Lines: {len(lines)}")
						print(f"Affected Stops: {len(stops)}")
						printList.append(heading)

	def do_trip(self, args):
		stationList = json.load(open("stationList.json"))
		completer = WordCompleter(stationList, ignore_case=True)
		origin = prompt(
			"Enter origin: ",
			completer=completer,
			complete_style=CompleteStyle.MULTI_COLUMN
		)
		destination = prompt(
			"Enter destination: ",
			completer=completer,
			complete_style=CompleteStyle.MULTI_COLUMN
		)
		url = f"{apiEndpoint}trip"
		params = {
			"outputFormat": "rapidJSON",
			"coordOutputFormat": "EPSG:4326",
			"depArrMacro": "dep",
			"itdDate": datetime.datetime.now().strftime("%Y%m%d"),
			"itdTime": datetime.datetime.now().strftime("%H%M"),
			"type_origin": "stop",
			"name_origin": origin,
			"type_destination": "stop",
			"name_destination": destination,
			"TfNSWTR": "true"
		}
		data = getData(url, params, headers)
		print(f"{origin} => {destination}")
		journeys =  data.get("journeys")
		print(len(journeys))

	def completenames(self, text, line, begidx, endidx):
		"""Override to provide autocompletion for commands."""
		return [cmd[3:] for cmd in self.get_names() if cmd.startswith(f"do_{text}")]

if __name__ == "__main__":
	cli = transportCLI()
	sys.exit(cli.cmdloop())
