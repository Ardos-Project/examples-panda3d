from direct.fsm.FSM import FSM
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import ConfigVariableString, WindowProperties

from ardos.ArdosClientRepository import ArdosClientRepository
from openworld.distributed import OpenWorldGlobals


class OpenWorldClientRepository(ArdosClientRepository, FSM):

    GameGlobalsId = OpenWorldGlobals.ROOT_DO_ID

    def __init__(self, username):
        ArdosClientRepository.__init__(self)
        FSM.__init__(self, "OpenWorldClientRepository")

        self.username = username
        self.serverVersion = ConfigVariableString("server-version", "").getValue()

        # Generate the AuthMgr uberdog object.
        self.authMgr = self.generateGlobalObject(
            OpenWorldGlobals.AUTH_MGR_DO_ID, "AuthMgr"
        )

        # Set the background color to black
        base.win.setClearColor((0, 0, 0, 1))
        # Update the window title to include our username.
        props = WindowProperties()
        props.setTitle(f"Open World Example - {self.username}")
        base.win.requestProperties(props)

        self.connectUrl = ""
        self.statusText = None

    def enterConnect(self, url):
        self.statusText = OnscreenText(
            text="Connecting...", fg=(1, 1, 1, 1), pos=(0, 0.00), scale=0.07
        )

        self.connectUrl = url
        self.connect(
            [url],
            successCallback=self._connectSuccess,
            failureCallback=self._connectFailed,
        )

    def exitConnect(self):
        self.statusText.destroy()

    def _connectSuccess(self):
        # We've connected to Ardos, say hello.
        self.acceptOnce(
            ArdosClientRepository.getHelloRespEvent(), lambda: self.demand("Login")
        )
        self.sendHello(self.serverVersion)

    def _connectFailed(self, statusCode, statusString):
        self.statusText.destroy()
        self.statusText = OnscreenText(
            text=f"Failed to connect to: {self.connectUrl}",
            fg=(1, 1, 1, 1),
            pos=(0, 0.00),
            scale=0.07,
        )

    def enterLogin(self):
        # We've connected to Ardos and have succesfulyl handshaked.
        self.startReaderPollTask()
        # Start sending heartbeats
        self.startHeartbeat()

        # Lets login now with the AuthMgr.
        self.statusText = OnscreenText(
            text="Authenticating...", fg=(1, 1, 1, 1), pos=(0, 0.00), scale=0.07
        )
        self.authMgr.login(self.username)

    def exitLogin(self):
        self.statusText.destroy()
