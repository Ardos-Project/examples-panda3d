import sys

from direct.task.TaskManagerGlobal import taskMgr
from panda3d.core import (
    CollisionTraverser,
    NodePath,
    PandaNode,
    CollisionNode,
    CollisionSphere,
    CollideMask,
    CollisionHandlerPusher,
    CollisionRay,
    CollisionHandlerQueue,
)

from openworld.distributed.DistributedPlayer import DistributedPlayer


class DistributedPlayerOV(DistributedPlayer):

    def __init__(self, cr):
        DistributedPlayer.__init__(self, cr)

        # This is used to store which keys are currently pressed.
        self.keyMap = {
            "left": 0,
            "right": 0,
            "forward": 0,
            "backward": 0,
            "cam-left": 0,
            "cam-right": 0,
        }

    def announceGenerate(self):
        DistributedPlayer.announceGenerate(self)

        # Setup local controls, camera, collision, etc.
        self.setupLocalPlayer()

    def setupLocalPlayer(self):
        # Create a floater object, which floats 2 units above ralph.  We
        # use this as a target for the camera to look at.

        self.floater = NodePath(PandaNode("floater"))
        self.floater.reparentTo(self.ralph)
        self.floater.setZ(2.0)

        # Accept the control keys for movement and rotation

        self.accept("escape", sys.exit)
        self.accept("arrow_left", self.setKey, ["left", True])
        self.accept("arrow_right", self.setKey, ["right", True])
        self.accept("arrow_up", self.setKey, ["forward", True])
        self.accept("arrow_down", self.setKey, ["backward", True])
        self.accept("a", self.setKey, ["cam-left", True])
        self.accept("s", self.setKey, ["cam-right", True])
        self.accept("arrow_left-up", self.setKey, ["left", False])
        self.accept("arrow_right-up", self.setKey, ["right", False])
        self.accept("arrow_up-up", self.setKey, ["forward", False])
        self.accept("arrow_down-up", self.setKey, ["backward", False])
        self.accept("a-up", self.setKey, ["cam-left", False])
        self.accept("s-up", self.setKey, ["cam-right", False])

        taskMgr.add(self.move, "moveTask")

        # Set up the camera
        self.disableMouse()
        self.camera.setPos(self.ralph.getX(), self.ralph.getY() + 10, 2)

        self.cTrav = CollisionTraverser()

        # Use a CollisionHandlerPusher to handle collisions between Ralph and
        # the environment. Ralph is added as a "from" object which will be
        # "pushed" out of the environment if he walks into obstacles.
        #
        # Ralph is composed of two spheres, one around the torso and one
        # around the head.  They are slightly oversized since we want Ralph to
        # keep some distance from obstacles.
        self.ralphCol = CollisionNode("ralph")
        self.ralphCol.addSolid(CollisionSphere(center=(0, 0, 2), radius=1.5))
        self.ralphCol.addSolid(CollisionSphere(center=(0, -0.25, 4), radius=1.5))
        self.ralphCol.setFromCollideMask(CollideMask.bit(0))
        self.ralphCol.setIntoCollideMask(CollideMask.allOff())
        self.ralphColNp = self.ralph.attachNewNode(self.ralphCol)
        self.ralphPusher = CollisionHandlerPusher()
        self.ralphPusher.horizontal = True

        # Note that we need to add ralph both to the pusher and to the
        # traverser; the pusher needs to know which node to push back when a
        # collision occurs!
        self.ralphPusher.addCollider(self.ralphColNp, self.ralph)
        self.cTrav.addCollider(self.ralphColNp, self.ralphPusher)

        # We will detect the height of the terrain by creating a collision
        # ray and casting it downward toward the terrain.  One ray will
        # start above ralph's head, and the other will start above the camera.
        # A ray may hit the terrain, or it may hit a rock or a tree.  If it
        # hits the terrain, we can detect the height.
        self.ralphGroundRay = CollisionRay()
        self.ralphGroundRay.setOrigin(0, 0, 9)
        self.ralphGroundRay.setDirection(0, 0, -1)
        self.ralphGroundCol = CollisionNode("ralphRay")
        self.ralphGroundCol.addSolid(self.ralphGroundRay)
        self.ralphGroundCol.setFromCollideMask(CollideMask.bit(0))
        self.ralphGroundCol.setIntoCollideMask(CollideMask.allOff())
        self.ralphGroundColNp = self.ralph.attachNewNode(self.ralphGroundCol)
        self.ralphGroundHandler = CollisionHandlerQueue()
        self.cTrav.addCollider(self.ralphGroundColNp, self.ralphGroundHandler)

        self.camGroundRay = CollisionRay()
        self.camGroundRay.setOrigin(0, 0, 9)
        self.camGroundRay.setDirection(0, 0, -1)
        self.camGroundCol = CollisionNode("camRay")
        self.camGroundCol.addSolid(self.camGroundRay)
        self.camGroundCol.setFromCollideMask(CollideMask.bit(0))
        self.camGroundCol.setIntoCollideMask(CollideMask.allOff())
        self.camGroundColNp = self.camera.attachNewNode(self.camGroundCol)
        self.camGroundHandler = CollisionHandlerQueue()
        self.cTrav.addCollider(self.camGroundColNp, self.camGroundHandler)

        # Uncomment this line to see the collision rays
        # self.ralphColNp.show()
        # self.camGroundColNp.show()

        # Uncomment this line to show a visual representation of the
        # collisions occuring
        # self.cTrav.showCollisions(render)

    # Records the state of the arrow keys
    def setKey(self, key, value):
        self.keyMap[key] = value

    # Accepts arrow keys to move either the player or the menu cursor,
    # Also deals with grid checking and collision detection
    def move(self, task):

        # Get the time that elapsed since last frame.  We multiply this with
        # the desired speed in order to find out with which distance to move
        # in order to achieve that desired speed.
        dt = base.clock.dt

        # If the camera-left key is pressed, move camera left.
        # If the camera-right key is pressed, move camera right.

        if self.keyMap["cam-left"]:
            self.camera.setX(self.camera, -20 * dt)
        if self.keyMap["cam-right"]:
            self.camera.setX(self.camera, +20 * dt)

        # If a move-key is pressed, move ralph in the specified direction.

        if self.keyMap["left"]:
            self.ralph.setH(self.ralph.getH() + 300 * dt)
        if self.keyMap["right"]:
            self.ralph.setH(self.ralph.getH() - 300 * dt)
        if self.keyMap["forward"]:
            self.ralph.setY(self.ralph, -20 * dt)
        if self.keyMap["backward"]:
            self.ralph.setY(self.ralph, +10 * dt)

        # If ralph is moving, loop the run animation.
        # If he is standing still, stop the animation.
        currentAnim = self.ralph.getCurrentAnim()

        if self.keyMap["forward"]:
            if currentAnim != "run":
                self.ralph.loop("run")
        elif self.keyMap["backward"]:
            # Play the walk animation backwards.
            if currentAnim != "walk":
                self.ralph.loop("walk")
            self.ralph.setPlayRate(-1.0, "walk")
        elif self.keyMap["left"] or self.keyMap["right"]:
            if currentAnim != "walk":
                self.ralph.loop("walk")
            self.ralph.setPlayRate(1.0, "walk")
        else:
            if currentAnim is not None:
                self.ralph.stop()
                self.ralph.pose("walk", 5)
                self.isMoving = False

        # If the camera is too far from ralph, move it closer.
        # If the camera is too close to ralph, move it farther.

        camvec = self.ralph.getPos() - self.camera.getPos()
        camvec.setZ(0)
        camdist = camvec.length()
        camvec.normalize()
        if camdist > 10.0:
            self.camera.setPos(self.camera.getPos() + camvec * (camdist - 10))
            camdist = 10.0
        if camdist < 5.0:
            self.camera.setPos(self.camera.getPos() - camvec * (5 - camdist))
            camdist = 5.0

        # Normally, we would have to call traverse() to check for collisions.
        # However, the class ShowBase that we inherit from has a task to do
        # this for us, if we assign a CollisionTraverser to self.cTrav.
        # self.cTrav.traverse(render)

        # Adjust ralph's Z coordinate.  If ralph's ray hit terrain,
        # update his Z

        entries = list(self.ralphGroundHandler.entries)
        entries.sort(key=lambda x: x.getSurfacePoint(render).getZ())

        for entry in entries:
            if entry.getIntoNode().name == "terrain":
                self.ralph.setZ(entry.getSurfacePoint(render).getZ())

        # Keep the camera at one unit above the terrain,
        # or two units above ralph, whichever is greater.

        entries = list(self.camGroundHandler.entries)
        entries.sort(key=lambda x: x.getSurfacePoint(render).getZ())

        for entry in entries:
            if entry.getIntoNode().name == "terrain":
                self.camera.setZ(entry.getSurfacePoint(render).getZ() + 1.5)
        if self.camera.getZ() < self.ralph.getZ() + 2.0:
            self.camera.setZ(self.ralph.getZ() + 2.0)

        # The camera should look in ralph's direction,
        # but it should also try to stay horizontal, so look at
        # a floater which hovers above ralph's head.
        self.camera.lookAt(self.floater)

        return task.cont
