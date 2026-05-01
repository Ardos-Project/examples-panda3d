from direct.directnotify import DirectNotifyGlobal

from ardos.ArdosInternalRepository import ArdosInternalRepository
from openworld.ai.DistributedDistrictAI import DistributedDistrictAI
from openworld.distributed import OpenWorldGlobals
from openworld.world.DistributedWorldAI import DistributedWorldAI


class OpenWorldAIRepository(ArdosInternalRepository):
    notify = DirectNotifyGlobal.directNotify.newCategory("OpenWorldAIRepository")
    notify.setInfo(True)

    GameGlobalsId = OpenWorldGlobals.ROOT_DO_ID

    def __init__(self, baseChannel, stateServerChannel, districtName):
        ArdosInternalRepository.__init__(
            self, baseChannel, serverId=stateServerChannel, dcSuffix="AI"
        )

        self.districtName = districtName

        self.districtId = 0
        self.distributedDistrict = None

        self.world = None

    def handleConnected(self):
        ArdosInternalRepository.handleConnected(self)

        # Tell Ardos who we are.
        # Helpful for debugging/logs.
        self.setConName(f"OpenWorldAI({self.districtName})")

        # Allocate an ID for our district object.
        self.districtId = self.allocateChannel()

        # Generate our DistributedDistrict object.
        # Part of the dynamic discovery mechanism for clients.
        self.distributedDistrict = DistributedDistrictAI(self)
        self.distributedDistrict.setName(self.districtName)
        self.distributedDistrict.generateWithRequiredAndId(
            self.districtId, self.getGameDoId(), OpenWorldGlobals.ZONE_ID_DISTRICTS
        )

        # Create the world for this district.
        self.world = DistributedWorldAI(self)
        self.world.generateWithRequired(OpenWorldGlobals.ZONE_ID_WORLD)

        # We've finished generating everything for this district.
        # Mark it as available for players to join.
        self.distributedDistrict.setAvailable(True)

        self.notify.info("Online!")
