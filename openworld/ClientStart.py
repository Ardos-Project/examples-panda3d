import os
import builtins

from direct.showbase.ShowBase import ShowBase
from dotenv import load_dotenv
from panda3d.core import *

from openworld.distributed.OpenWorldClientRepository import OpenWorldClientRepository

# Load environment variables from .env
load_dotenv()

localconfig = f"cr-connect {os.getenv('CR_CONNECT', 'g://127.0.0.1:25565')}"

loadPrcFileData("Command-line", localconfig)

loadPrcFile("config/openworld.prc")


class game:
    name = "openworld"
    process = "client"


builtins.game = game

host = ConfigVariableString("cr-connect").value

username = input("Username: ")

base = ShowBase()
base.cr = OpenWorldClientRepository(username)
base.cr.demand("Connect", host)

try:
    base.run()
except SystemExit:
    raise
except Exception:
    raise
