"""instantiate global ShowBase object"""

import builtins
from typing import Any

from panda3d.core import Notify
from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.task.TaskManagerGlobal import taskMgr

from ardos.ai.AIBase import AIBase

# Injected into builtins by the host application.
game: Any
__dev__: bool

# guard against AI files being imported on the client
assert game.process != "client"

simbase = AIBase()
builtins.simbase = simbase

# Make some global aliases for convenience
builtins.ostream = Notify.out()
builtins.run = simbase.run
builtins.taskMgr = simbase.taskMgr
builtins.jobMgr = simbase.jobMgr
builtins.eventMgr = simbase.eventMgr
builtins.messenger = simbase.messenger
builtins.bboard = simbase.bboard
builtins.config = simbase.config
builtins.directNotify = directNotify

from direct.showbase import Loader

simbase.loader = Loader.Loader(simbase)
builtins.loader = simbase.loader

# Set direct notify categories now that we have config
directNotify.setDconfigLevels()


def inspect(anObject: Any) -> None:
    from direct.tkpanels import Inspector

    Inspector.inspect(anObject)


builtins.inspect = inspect
# this also appears in ShowBaseGlobal
if (not __debug__) and __dev__:
    notify = directNotify.newCategory("ShowBaseGlobal")
    notify.error("You must set 'want-dev' to false in non-debug mode.")


# Now the builtins are filled in.
taskMgr.finalInit()
