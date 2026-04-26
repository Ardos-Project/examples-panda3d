import time
import builtins
from typing import Any

from panda3d.core import (
    ClockObject,
    ConfigVariableBool,
    ConfigVariableDouble,
    ConfigVariableInt,
    GraphicsEngine,
    NodePath,
    Notify,
    PandaNode,
    PStatClient,
    TrueClock,
    VirtualFileSystem,
    loadPrcFileData,
)
from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.showbase.MessengerGlobal import messenger
from direct.showbase.BulletinBoardGlobal import bulletinBoard
from direct.task.TaskManagerGlobal import taskMgr
from direct.showbase.JobManagerGlobal import jobMgr
from direct.showbase.EventManagerGlobal import eventMgr
from direct.interval.IntervalManager import ivalMgr
from direct.task import Task
from direct.showbase import ExceptionVarDump
from direct.showbase import DConfig

# These names are injected into builtins at runtime (by the host application or
# by AIBaseGlobal). Bare annotations make them visible to mypy without binding
# any value at import time -- the lookup falls through to builtins.
game: Any
__dev__: bool
globalClock: Any

# assert game.process == 'ai', "Are you intentionally running ai code on %s"%(game.process,)


class AIBase:
    notify = directNotify.newCategory("AIBase")

    def __init__(self):
        # Get the dconfig object
        self.config = DConfig
        builtins.__dev__ = ConfigVariableBool("want-dev", __debug__).getValue()
        if ConfigVariableBool("want-variable-dump", False).getValue():
            ExceptionVarDump.install()

        if ConfigVariableBool("use-vfs", True).getValue():
            vfs = VirtualFileSystem.getGlobalPtr()
        else:
            vfs = None

        # Store dconfig variables
        self.wantTk = ConfigVariableBool("want-tk", False).getValue()

        # How long should the AI sleep between frames to keep CPU usage down
        self.AISleep = ConfigVariableDouble("ai-sleep", 0.04).getValue()
        self.AIRunningNetYield = ConfigVariableBool(
            "ai-running-net-yield", False
        ).getValue()
        self.AIForceSleep = ConfigVariableBool("ai-force-sleep", False).getValue()
        self.eventMgr = eventMgr
        self.messenger = messenger
        self.bboard = bulletinBoard

        self.taskMgr = taskMgr
        Task.TaskManager.taskTimerVerbose = ConfigVariableBool(
            "task-timer-verbose", False
        ).getValue()
        Task.TaskManager.extendedExceptions = ConfigVariableBool(
            "extended-exceptions", False
        ).getValue()

        self.sfxManagerList = None
        self.musicManager = None
        self.jobMgr = jobMgr

        self.hidden = NodePath("hidden")
        # each zone has its own render
        self.render = NodePath("render")

        # This graphics engine is not intended to ever draw anything, it
        # advanced clocks and clears pstats state, just like on the client.
        self.graphicsEngine = GraphicsEngine()

        # Get a pointer to Panda's global ClockObject, used for
        # synchronizing events between Python and C.
        # object is exactly in sync with the TrueClock.
        globalClock = ClockObject.getGlobalClock()

        # Since we have already started up a TaskManager, and probably
        # a number of tasks; and since the TaskManager had to use the
        # TrueClock to tell time until this moment, make sure the
        # globalClock
        self.trueClock = TrueClock.getGlobalPtr()
        globalClock.setRealTime(self.trueClock.getShortTime())
        # set the amount of time used to compute average frame rate
        globalClock.setAverageFrameRateInterval(30.0)
        globalClock.tick()

        # Now we can make the TaskManager start using the new globalClock.
        taskMgr.globalClock = globalClock

        builtins.ostream = Notify.out()
        builtins.globalClock = globalClock
        builtins.vfs = vfs
        builtins.hidden = self.hidden
        builtins.render = self.render

        AIBase.notify.info("__dev__ == %s" % __dev__)

        # This is temporary:
        builtins.wantTestObject = ConfigVariableBool(
            "want-test-object", False
        ).getValue()

        self.wantStats = ConfigVariableBool("want-pstats", False).getValue()
        Task.TaskManager.pStatsTasks = ConfigVariableBool(
            "pstats-tasks", False
        ).getValue()
        # Set up the TaskManager to reset the PStats clock back
        # whenever we resume from a pause.  This callback function is
        # a little hacky, but we can't call it directly from within
        # the TaskManager because he doesn't know about PStats (and
        # has to run before libpanda is even loaded).
        taskMgr.resumeFunc = PStatClient.resumeAfterPause

        # in production, we want to use fake textures.
        defaultValue = True
        if __dev__:
            defaultValue = False
        wantFakeTextures = ConfigVariableBool(
            "want-fake-textures-ai", defaultValue
        ).getValue()

        if wantFakeTextures:
            # Setting textures-header-only is a little better than
            # using fake-texture-image.  The textures' headers are
            # read to check their number of channels, etc., and then a
            # 1x1 blue texture is created.  It loads quickly, consumes
            # very little memory, and doesn't require a bogus texture
            # to be loaded repeatedly.
            loadPrcFileData("aibase", "textures-header-only #t")

        # If there's a Toontown-specific AIBase, that's where the following
        # config flags should be.
        # I tried putting this logic in ToontownAIRepository, but wantPets is
        # needed during the import of ToontownAIRepository.py
        self.wantPets = ConfigVariableBool("want-pets", True).getValue()
        if self.wantPets:
            if game.name == "toontown":
                from toontown.pets import PetConstants

                self.petMoodTimescale = ConfigVariableDouble(
                    "pet-mood-timescale", 1.0
                ).getValue()
                self.petMoodDriftPeriod = ConfigVariableDouble(
                    "pet-mood-drift-period", PetConstants.MoodDriftPeriod
                ).getValue()
                self.petThinkPeriod = ConfigVariableDouble(
                    "pet-think-period", PetConstants.ThinkPeriod
                ).getValue()
                self.petMovePeriod = ConfigVariableDouble(
                    "pet-move-period", PetConstants.MovePeriod
                ).getValue()
                self.petPosBroadcastPeriod = ConfigVariableDouble(
                    "pet-pos-broadcast-period", PetConstants.PosBroadcastPeriod
                ).getValue()

        self.wantBingo = ConfigVariableBool("want-fish-bingo", True).getValue()
        self.wantKarts = ConfigVariableBool("wantKarts", True).getValue()

        self.newDBRequestGen = ConfigVariableBool(
            "new-database-request-generate", True
        ).getValue()

        self.waitShardDelete = ConfigVariableBool("wait-shard-delete", True).getValue()
        self.blinkTrolley = ConfigVariableBool("blink-trolley", False).getValue()
        self.fakeDistrictPopulations = ConfigVariableBool(
            "fake-district-populations", False
        ).getValue()

        self.wantSwitchboard = ConfigVariableBool("want-switchboard", False).getValue()
        self.wantSwitchboardHacks = ConfigVariableBool(
            "want-switchboard-hacks", False
        ).getValue()
        self.GEMdemoWhisperRecipientDoid = ConfigVariableBool(
            "gem-demo-whisper-recipient-doid", False
        ).getValue()
        self.sqlAvailable = ConfigVariableBool("sql-available", True).getValue()

        self.createStats()

        self.restart()

        ## ok lets over ride the time yieldFunction
        # self.MaxEpockSpeed = 1.0/60.0;
        # taskMgr.doYield = self.taskManagerDoYield;

    def setupCpuAffinities(self, minChannel):
        if game.name == "uberDog":
            affinityMask = ConfigVariableInt("uberdog-cpu-affinity-mask", -1).getValue()
        else:
            affinityMask = ConfigVariableInt("ai-cpu-affinity-mask", -1).getValue()
        if affinityMask != -1:
            TrueClock.getGlobalPtr().setCpuAffinity(affinityMask)
        else:
            # this is useful on machines that perform better with each process
            # assigned to a single CPU
            autoAffinity = ConfigVariableBool(
                "auto-single-cpu-affinity", False
            ).getValue()
            if game.name == "uberDog":
                affinity = ConfigVariableInt("uberdog-cpu-affinity", -1).getValue()
                if autoAffinity and (affinity == -1):
                    affinity = 2
            else:
                affinity = ConfigVariableInt("ai-cpu-affinity", -1).getValue()
                if autoAffinity and (affinity == -1):
                    affinity = 1
            if affinity != -1:
                TrueClock.getGlobalPtr().setCpuAffinity(1 << affinity)
            elif autoAffinity:
                if game.name == "uberDog":
                    # set the affinity based on our channel range
                    channelSet = int(minChannel / 1000000)
                    channelSet -= 240
                    # add an offset so that the default uberdog affinity is 2
                    affinity = channelSet + 3
                    # this could be better if we know how many CPUs we have
                    # for now spread the uberdogs across 4 processors
                    TrueClock.getGlobalPtr().setCpuAffinity(1 << (affinity % 4))

    #########################################################################
    # This is the yield function for simple timing based .. no consideration for Network and such..
    ###########################################################################
    def taskManagerDoYield(self, frameStartTime, nextScheuledTaksTime):
        minFinTime = frameStartTime + self.MaxEpockSpeed
        if nextScheuledTaksTime > 0 and nextScheuledTaksTime < minFinTime:
            minFinTime = nextScheuledTaksTime

        delta = minFinTime - globalClock.getRealTime()
        while delta > 0.002:
            time.sleep(delta)
            delta = minFinTime - globalClock.getRealTime()

    def createStats(self, hostname=None, port=None):
        # You can specify pstats-host in your Config.prc or use ~pstats/~aipstats
        # The default is localhost
        if not self.wantStats:
            return False

        if PStatClient.isConnected():
            PStatClient.disconnect()
        # these default values match the C++ default values
        if hostname is None:
            hostname = ""
        if port is None:
            port = -1
        PStatClient.connect(hostname, port)
        return PStatClient.isConnected()

    def __sleepCycleTask(self, task):
        # To keep the AI task from running too fast, we sleep a bit here
        time.sleep(self.AISleep)
        return Task.cont

    def __resetPrevTransform(self, state):
        # Clear out the previous velocity deltas now, after we have
        # rendered (the previous frame).  We do this after the render,
        # so that we have a chance to draw a representation of spheres
        # along with their velocities.  At the beginning of the frame
        # really means after the command prompt, which allows the user
        # to interactively query these deltas meaningfully.

        PandaNode.resetAllPrevTransform()
        return Task.cont

    def __ivalLoop(self, state):
        # Execute all intervals in the global ivalMgr.
        ivalMgr.step()
        return Task.cont

    def __igLoop(self, state):
        # This advances the clocks and clears pstats state
        self.graphicsEngine.renderFrame()
        return Task.cont

    def shutdown(self):
        self.taskMgr.remove("ivalLoop")
        self.taskMgr.remove("igLoop")
        self.taskMgr.remove("aiSleep")
        self.eventMgr.shutdown()

    def restart(self):
        self.shutdown()
        # __resetPrevTransform goes at the very beginning of the frame.
        self.taskMgr.add(self.__resetPrevTransform, "resetPrevTransform", priority=-51)
        # spawn the ivalLoop with a later priority, so that it will
        # run after most tasks, but before igLoop.
        self.taskMgr.add(self.__ivalLoop, "ivalLoop", priority=20)
        self.taskMgr.add(self.__igLoop, "igLoop", priority=50)
        if self.AISleep >= 0 and (not self.AIRunningNetYield or self.AIForceSleep):
            self.taskMgr.add(self.__sleepCycleTask, "aiSleep", priority=55)

        self.eventMgr.restart()

    def getRepository(self):
        return self.air

    def run(self):
        self.taskMgr.run()
