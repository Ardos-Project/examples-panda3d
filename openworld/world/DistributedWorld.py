from direct.distributed.DistributedCartesianGrid import DistributedCartesianGrid
from panda3d.core import AmbientLight, DirectionalLight


class DistributedWorld(DistributedCartesianGrid):

    def __init__(self, cr):
        DistributedCartesianGrid.__init__(self, cr)

        self.environ = None
        self.ambientLight = None
        self.directionalLight = None

    def announceGenerate(self):
        DistributedCartesianGrid.announceGenerate(self)

        # Set up the environment
        #
        # This environment model contains collision meshes.  If you look
        # in the egg file, you will see the following:
        #
        #    <Collide> { Polyset keep descend }
        #
        # This tag causes the following mesh to be converted to a collision
        # mesh -- a mesh which is optimized for collision, not rendering.
        # It also keeps the original mesh, so there are now two copies ---
        # one optimized for rendering, one for collisions.

        self.environ = loader.loadModel("models/world")
        self.environ.reparentTo(render)

        # We do not have a skybox, so we will just use a sky blue background color
        self.setBackgroundColor(0.53, 0.80, 0.92, 1)

        # Create some lighting
        self.ambientLight = AmbientLight("ambientLight")
        self.ambientLight.setColor((0.3, 0.3, 0.3, 1))

        self.directionalLight = DirectionalLight("directionalLight")
        self.directionalLight.setDirection((-5, -5, -5))
        self.directionalLight.setColor((1, 1, 1, 1))
        self.directionalLight.setSpecularColor((1, 1, 1, 1))

        render.setLight(render.attachNewNode(self.ambientLight))
        render.setLight(render.attachNewNode(self.directionalLight))

    def delete(self):
        """
        Make sure we clean up after ourselves if the world goes away.
        :return:
        """
        # Remove the world model.
        self.environ.removeNode()
        # Remove lighting.
        self.ambientLight.removeNode()
        self.directionalLight.removeNode()

        DistributedCartesianGrid.delete(self)
