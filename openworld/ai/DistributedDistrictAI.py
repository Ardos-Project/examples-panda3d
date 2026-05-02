import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from openworld.distributed import OpenWorldGlobals


class DistributedDistrictAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedDistrictAI")

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)

        self.name = ""
        self.available = False
        self.population = 0

    def requestJoin(self):
        """
        A client is requesting to join this district.
        :return:
        """
        avatarId = self.air.getAvatarIdFromSender()
        if not avatarId:
            return

        # If we're not ready to start accepting players (still starting up),
        # reject their request.
        if not self.available:
            return

        # Have they already joined this district?
        # If they have, we'll be their managing AI,
        # and they'll have been generated on us already.
        if self.air.doId2do.get(avatarId):
            self.notify.warning(
                f"{avatarId} requested to join our district when they already have."
            )
            return

        # We could check population levels, etc., here and reject the request if we wanted to.
        # We don't bother with any of that, but an example is below:
        # if <don't allow client to join>:
        #   self.sendUpdateToAvatarId(avatarId, "rejectJoin", ["This district is full!"])

        # The client *needs* to be able to see any objects it's parented under,
        # otherwise it will have no idea what we're talking about.
        # Give it visibility of the world before we move it under.
        self.air.clientAddInterest(
            self.GetPuppetConnectionChannel(avatarId),
            OpenWorldGlobals.INTEREST_HANDLE_CLIENT_WORLD,
            self.air.districtId,
            OpenWorldGlobals.ZONE_ID_WORLD,
        )

        # Alright, let's set the location of the avatar underneath us.
        # We'll put them underneath the world we generated in DistributedDistrict.
        # Use zone 0 (invalid) for their initial zone, the world will start calculating their correct
        # zone based on their XYZ position.
        self.air.sendSetLocationDoId(avatarId, self.air.world.doId, 0)

    def setName(self, name):
        self.name = name

    def getName(self):
        return self.name

    def setAvailable(self, available):
        self.available = available

    def d_setAvailable(self, available):
        self.sendUpdate("setAvailable", [available])

    def b_setAvailable(self, available):
        self.setAvailable(available)
        self.d_setAvailable(available)

    def getAvailable(self):
        return self.available

    def setPopulation(self, population):
        self.population = population

    def d_setPopulation(self, population):
        self.sendUpdate("setPopulation", [population])

    def b_setPopulation(self, population):
        self.setPopulation(population)
        self.d_setPopulation(population)

    def getPopulation(self):
        return self.population
