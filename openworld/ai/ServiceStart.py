import os
import builtins

from dotenv import load_dotenv
from panda3d.core import *

# Load environment variables from .env
load_dotenv()

localconfig = f"air-base-channel {int(os.getenv('AIR_BASE_CHANNEL', '401000000'))}\n"
localconfig += (
    f"air-channel-allocation {int(os.getenv('AIR_CHANNEL_ALLOC', '1000000'))}\n"
)
localconfig += f"air-stateserver {int(os.getenv('AIR_STATESERVER', '1001'))}\n"
localconfig += f"air-connect {os.getenv('AIR_CONNECT', '127.0.0.1')}\n"
localconfig += f"district-name {os.getenv('DISTRICT_NAME', 'Devhaven')}\n"

loadPrcFileData("Command-line", localconfig)

loadPrcFile("../config/openworld.prc")


class game:
    name = "openworld"
    process = "server"


builtins.game = game

from ardos.ai.AIBaseGlobal import *

from openworld.ai.OpenWorldAIRepository import OpenWorldAIRepository

simbase.air = OpenWorldAIRepository(
    ConfigVariableInt("air-base-channel").value,
    ConfigVariableInt("air-stateserver").value,
    ConfigVariableString("district-name").value,
)

host = ConfigVariableString("air-connect").value
port = 7199
if ":" in host:
    host, port = host.split(":", 1)
    port = int(port)

simbase.air.connect(host, port)

try:
    simbase.run()
except SystemExit:
    raise
except Exception:
    raise
