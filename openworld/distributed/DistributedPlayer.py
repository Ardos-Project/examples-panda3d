from direct.actor.Actor import Actor
from direct.distributed.DistributedSmoothNode import DistributedSmoothNode
from panda3d.core import TextNode


class DistributedPlayer(DistributedSmoothNode):

    def __init__(self, cr):
        DistributedSmoothNode.__init__(self, cr)

        self.name = ""
        self.ralph = None
        self.nameText = None
        self.nameNP = None

    def announceGenerate(self):
        DistributedSmoothNode.announceGenerate(self)

        # Create the visual representation of the player.
        self.setupPlayer()
        self.reparentTo(render)

        # Start smoothing/lerping the players position.
        self.activateSmoothing(True, True)
        self.startSmooth()

    def delete(self):
        """
        Make sure we clean up after ourselves when a player is no longer visible.
        :return:
        """
        # Stop smoothing and remove the model.
        self.stopSmooth()
        self.detachNode()

        DistributedSmoothNode.delete(self)

    def setName(self, name):
        self.name = name

    def getName(self):
        return self.name

    def setupPlayer(self):
        # Setup the Actor (model, animations, etc.)
        self.ralph = Actor(
            "models/ralph", {"run": "models/ralph-run", "walk": "models/ralph-walk"}
        )
        self.ralph.reparentTo(self)
        self.ralph.setScale(0.2)

        # Setup their nametag.
        self.nameText = TextNode("%d-nameText" % self.doId)
        self.nameText.setText(self.name)
        self.nameText.setAlign(self.nameText.A_center)

        self.nameNP = self.attachNewNode(self.nameText)
        self.nameNP.setScale(0.25)
        self.nameNP.setPos(0, 0, 1.2)
        self.nameNP.setBillboardPointEye()
