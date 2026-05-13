import math
import sys

from direct.directnotify import DirectNotifyGlobal
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
    WindowProperties,
)

from openworld.distributed.DistributedPlayer import DistributedPlayer


class DistributedPlayerOV(DistributedPlayer):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPlayerOV")

    # Camera tuning.
    CAM_DIST_MIN = 4.0
    CAM_DIST_MAX = 25.0
    CAM_DIST_DEFAULT = 10.0
    CAM_ZOOM_STEP = 1.5
    CAM_PITCH_MIN = 2.0
    CAM_PITCH_MAX = 80.0
    CAM_PITCH_DEFAULT = 12.0
    CAM_SENSITIVITY_X = 0.25  # degrees of yaw per pixel of mouse delta
    CAM_SENSITIVITY_Y = 0.20  # degrees of pitch per pixel of mouse delta
    CAM_SNAP_RATE = 6.0  # exponential rate (per second) for snapping yaw back

    def __init__(self, cr):
        DistributedPlayer.__init__(self, cr)

        # This is used to store which keys are currently pressed.
        self.keyMap = {
            "left": 0,
            "right": 0,
            "forward": 0,
            "backward": 0,
        }

        # Orbit camera state. camYaw is world-space (degrees, CCW around Z from +Y),
        # so "directly behind ralph" corresponds to camYaw == ralph.getH().
        self.camYaw = 0.0
        self.camPitch = self.CAM_PITCH_DEFAULT
        self.camDistance = self.CAM_DIST_DEFAULT
        self.rightDragging = False
        self.lastMousePos = None

        self.colliding = False

    def isLocal(self):
        return True

    def announceGenerate(self):
        DistributedPlayer.announceGenerate(self)

        self.cr.doId2do[self.doId] = self

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
        self.accept("arrow_left-up", self.setKey, ["left", False])
        self.accept("arrow_right-up", self.setKey, ["right", False])
        self.accept("arrow_up-up", self.setKey, ["forward", False])
        self.accept("arrow_down-up", self.setKey, ["backward", False])
        self.accept("a", self.setKey, ["left", True])
        self.accept("d", self.setKey, ["right", True])
        self.accept("w", self.setKey, ["forward", True])
        self.accept("s", self.setKey, ["backward", True])
        self.accept("a-up", self.setKey, ["left", False])
        self.accept("d-up", self.setKey, ["right", False])
        self.accept("w-up", self.setKey, ["forward", False])
        self.accept("s-up", self.setKey, ["backward", False])

        # Orbit camera: hold right-click to drag-rotate, mouse wheel to zoom.
        self.accept("mouse3", self.startCamDrag)
        self.accept("mouse3-up", self.stopCamDrag)
        self.accept("wheel_up", self.zoomCam, [-1])
        self.accept("wheel_down", self.zoomCam, [1])

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
        self.ralphPusher.addCollider(self.ralphColNp, self)

        # We will detect the height of the terrain by creating a collision
        # ray and casting it downward toward the terrain.  One ray will
        # start above ralph's head, and the other will start above the camera.
        # A ray may hit the terrain, or it may hit a rock or a tree.  If it
        # hits the terrain, we can detect the height.
        self.ralphGroundRay = CollisionRay()
        # Start the ray high above any terrain peak in the world so the
        # downward cast always reaches the surface, even right after spawn.
        # A ray that starts under the terrain finds no hit and the player
        # remains clipped below the mesh until they walk to lower ground.
        self.ralphGroundRay.setOrigin(0, 0, 1000)
        self.ralphGroundRay.setDirection(0, 0, -1)
        self.ralphGroundCol = CollisionNode("ralphRay")
        self.ralphGroundCol.addSolid(self.ralphGroundRay)
        self.ralphGroundCol.setFromCollideMask(CollideMask.bit(0))
        self.ralphGroundCol.setIntoCollideMask(CollideMask.allOff())
        self.ralphGroundColNp = self.ralph.attachNewNode(self.ralphGroundCol)
        self.ralphGroundHandler = CollisionHandlerQueue()

        self.camGroundRay = CollisionRay()
        self.camGroundRay.setOrigin(0, 0, 1000)
        self.camGroundRay.setDirection(0, 0, -1)
        self.camGroundCol = CollisionNode("camRay")
        self.camGroundCol.addSolid(self.camGroundRay)
        self.camGroundCol.setFromCollideMask(CollideMask.bit(0))
        self.camGroundCol.setIntoCollideMask(CollideMask.allOff())
        self.camGroundColNp = base.camera.attachNewNode(self.camGroundCol)
        self.camGroundHandler = CollisionHandlerQueue()

        # Uncomment this line to see the collision rays
        # self.ralphColNp.show()
        # self.camGroundColNp.show()

        # Uncomment this line to show a visual representation of the
        # collisions occuring
        # self.cTrav.showCollisions(render)

    def setLocation(self, parentId, zoneId, teleport=0):
        super().setLocation(parentId, zoneId, teleport)

        # If we've been parented underneath a grid (the world), set up our local controls.
        # Otherwise, disable them.
        if self.gridParent:
            self.collisionsOn()
        else:
            self.collisionsOff()

    def collisionsOn(self):
        if self.colliding:
            return

        self.colliding = True

        # Set up the camera
        base.disableMouse()
        # Start the camera directly behind ralph at the default pitch/distance.
        self.camYaw = self.getH(render)
        self.camPitch = self.CAM_PITCH_DEFAULT
        self.camDistance = self.CAM_DIST_DEFAULT
        self.rightDragging = False
        self.lastMousePos = None
        self._placeCamera()

        self.cTrav.addCollider(self.ralphColNp, self.ralphPusher)
        self.cTrav.addCollider(self.ralphGroundColNp, self.ralphGroundHandler)
        self.cTrav.addCollider(self.camGroundColNp, self.camGroundHandler)

        taskMgr.add(self.move, "moveTask")

        # Start broadcasting our position to the server.
        self.startPosHprBroadcast()

    def collisionsOff(self):
        if not self.colliding:
            return

        self.colliding = False

        # Stop broadcasting our position.
        self.stopPosHprBroadcast()

        taskMgr.remove("moveTask")
        base.enableMouse()

        # Make sure the cursor is restored if we were mid-drag.
        self.rightDragging = False
        self.lastMousePos = None
        self._setCursorHidden(False)

        self.cTrav.removeCollider(self.ralphColNp)
        self.cTrav.removeCollider(self.ralphGroundColNp)
        self.cTrav.removeCollider(self.camGroundColNp)

    # Records the state of the arrow keys
    def setKey(self, key, value):
        self.keyMap[key] = value

    def startCamDrag(self):
        self.rightDragging = True
        # Anchor the cursor to the center while dragging so we get unbounded deltas.
        cx, cy = self._winCenter()
        if base.win is not None:
            base.win.movePointer(0, cx, cy)
        self.lastMousePos = (cx, cy)
        self._setCursorHidden(True)

    def stopCamDrag(self):
        self.rightDragging = False
        self.lastMousePos = None
        self._setCursorHidden(False)

    def _winCenter(self):
        if base.win is None:
            return (0, 0)
        return (base.win.getXSize() // 2, base.win.getYSize() // 2)

    def _setCursorHidden(self, hidden):
        if base.win is None:
            return
        props = WindowProperties()
        props.setCursorHidden(hidden)
        base.win.requestProperties(props)

    def zoomCam(self, direction):
        self.camDistance = max(
            self.CAM_DIST_MIN,
            min(self.CAM_DIST_MAX, self.camDistance + direction * self.CAM_ZOOM_STEP),
        )

    def _isMoving(self):
        return bool(
            self.keyMap["forward"]
            or self.keyMap["backward"]
            or self.keyMap["left"]
            or self.keyMap["right"]
        )

    def _placeCamera(self):
        # Compute camera position from spherical coords around ralph.
        # camYaw=0 puts the camera at +Y from ralph; ralph faces -Y at H=0,
        # so "behind ralph" world yaw == ralph.getH(render).
        yawRad = math.radians(self.camYaw)
        pitchRad = math.radians(self.camPitch)
        cosP = math.cos(pitchRad)
        offX = -math.sin(yawRad) * self.camDistance * cosP
        offY = math.cos(yawRad) * self.camDistance * cosP
        offZ = math.sin(pitchRad) * self.camDistance
        ralphPos = self.getPos(render)
        base.camera.setPos(
            ralphPos[0] + offX,
            ralphPos[1] + offY,
            ralphPos[2] + 2.0 + offZ,
        )

    # Accepts arrow keys to move either the player or the menu cursor,
    # Also deals with grid checking and collision detection
    def move(self, task):

        # Get the time that elapsed since last frame.  We multiply this with
        # the desired speed in order to find out with which distance to move
        # in order to achieve that desired speed.
        dt = base.clock.dt

        # If a move-key is pressed, move ralph in the specified direction.

        if self.keyMap["left"]:
            self.setH(self.getH() + 300 * dt)
        if self.keyMap["right"]:
            self.setH(self.getH() - 300 * dt)
        if self.keyMap["forward"]:
            self.setY(self.ralph, -20 * dt)
        if self.keyMap["backward"]:
            self.setY(self.ralph, +10 * dt)

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

        # Update the orbit camera angles. Right-click drag rotates freely;
        # otherwise, if the player is moving, smoothly snap yaw back behind ralph.
        if self.rightDragging and base.win is not None and base.win.hasPointer(0):
            p = base.win.getPointer(0)
            mx, my = p.getX(), p.getY()
            cx, cy = self._winCenter()
            # Deltas are measured from the window center, then we snap the
            # pointer back so it can never drift off the window edge.
            dx = mx - cx
            dy = my - cy
            if dx or dy:
                self.camYaw -= dx * self.CAM_SENSITIVITY_X
                self.camPitch = max(
                    self.CAM_PITCH_MIN,
                    min(
                        self.CAM_PITCH_MAX, self.camPitch + dy * self.CAM_SENSITIVITY_Y
                    ),
                )
                base.win.movePointer(0, cx, cy)
            self.lastMousePos = (cx, cy)
        elif self._isMoving():
            targetYaw = self.getH(render)
            # Wrap the difference into [-180, 180] so we lerp the short way around.
            diff = ((targetYaw - self.camYaw + 180.0) % 360.0) - 180.0
            factor = 1.0 - math.exp(-self.CAM_SNAP_RATE * dt)
            self.camYaw += diff * factor

        self._placeCamera()

        # Normally, we would have to call traverse() to check for collisions.
        # However, the class ShowBase that we inherit from has a task to do
        # this for us, if we assign a CollisionTraverser to self.cTrav.
        self.cTrav.traverse(render)

        # Adjust ralph's Z coordinate.  If ralph's ray hit terrain,
        # update his Z

        entries = list(self.ralphGroundHandler.entries)
        entries.sort(key=lambda x: x.getSurfacePoint(render).getZ())

        for entry in entries:
            if entry.getIntoNode().name == "terrain":
                self.setZ(render, entry.getSurfacePoint(render).getZ())

        # Lift the camera if it would clip into the terrain. Unlike the original
        # implementation we only lift, never snap downwards, so a high-pitched
        # orbit view can stay elevated.

        entries = list(self.camGroundHandler.entries)
        entries.sort(key=lambda x: x.getSurfacePoint(render).getZ())

        for entry in entries:
            if entry.getIntoNode().name == "terrain":
                minZ = entry.getSurfacePoint(render).getZ() + 1.5
                if base.camera.getZ() < minZ:
                    base.camera.setZ(minZ)
        if base.camera.getZ() < self.getZ(render) + 2.0:
            base.camera.setZ(self.getZ(render) + 2.0)

        # The camera should look in ralph's direction,
        # but it should also try to stay horizontal, so look at
        # a floater which hovers above ralph's head.
        base.camera.lookAt(self.floater)

        return task.cont
