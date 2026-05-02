import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedCartesianGridAI import DistributedCartesianGridAI
from direct.distributed.DistributedSmoothNodeAI import DistributedSmoothNodeAI

from openworld.distributed.DistributedPlayerAI import DistributedPlayerAI


class DistributedWorldAI(DistributedCartesianGridAI):
    """
    The "World" that players and visible Distributed Objects are parented under.
    The combination of `setParentingRules` in the dc definition for this class and the values
    below drive the behavior of surrounding grids being visible, while only having location under one grid.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedWorldAI")

    # You can play around with these values to see how the generated
    # grid grows/shrinks, and how many surrounding objects you can see.

    # N.B. `setParentingRules` of DistributedWorld in config/openworld.dc will need to be updated
    # if you modify these values.
    # That's because parenting rules are used by Ardos to calculate/open surrounding grid interest,
    # whereas the values here are used by the AI to actually set the players location as they move around.

    # Gives us a large buffer as a starting point.
    # Note that zones are uint32's, and cannot be negative.
    # You want to calculate your starting zone center out so that it covers the whole world.
    WORLD_STARTING_ZONE = 500
    # How many grids do we want to actually generate?
    # This number should cover your whole world.
    # This is a Length x Width, e.g. 20 = 20x20 = 400
    WORLD_GRID_SIZE = 20
    # How many surrounding grids do we want interest in (i.e. visible to the client).
    # 1 = 3x3, 2 = 9x9, etc.
    WORLD_GRID_RADIUS = 1
    # The width of the cells in game units.
    # This is used along with an avatar/objects position to calculate which grid they're standing in.
    WORLD_CELL_WIDTH = 15

    # `setParentingRules` with these values would look like:
    # setParentingRules(string type="Cartesian", string Rule="500:20:1") broadcast ram;

    def __init__(self, air):
        DistributedCartesianGridAI.__init__(
            self,
            air,
            self.WORLD_STARTING_ZONE,
            self.WORLD_GRID_SIZE,
            self.WORLD_GRID_RADIUS,
            self.WORLD_CELL_WIDTH,
        )

        # Load the world model.
        # We need the starting spawn location, this won't be rendered at all on the server.
        # In a real world project, you'd want to use JSON or some binary format for world data.
        self.environ = loader.loadModel("../models/world")
        self.startPos = self.environ.find("**/start_point").getPos()

    def handleChildArrive(self, childObj, zoneId):
        # If it's a player, give them an initial spawn position.
        if isinstance(childObj, DistributedPlayerAI):
            # Make it a little random.
            childObj.setPos(
                self.startPos + (random.randint(-10, 10), random.randint(-10, 10), 0.5)
            )

        # If a child distributed object arrives underneath us,
        # and it's one we expect to move around (is/inherits DistributedSmoothNode),
        # make sure we explicitly add them to the grid so we can calculate their location based on their position.
        if isinstance(childObj, DistributedSmoothNodeAI):
            self.addObjectToGrid(childObj)

    def handleChildLeave(self, childObj, zoneId):
        # A "moving" object is leaving us, stop tracking their position.
        if isinstance(childObj, DistributedSmoothNodeAI):
            self.removeObjectFromGrid(childObj)
