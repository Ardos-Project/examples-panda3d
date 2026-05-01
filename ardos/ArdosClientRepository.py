"""ArdosClientRepository module: contains the ArdosClientRepository class"""

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClientRepositoryBase import ClientRepositoryBase
from direct.distributed.MsgTypes import *
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from direct.showbase.ShowBaseGlobal import globalClock
from direct.task.TaskManagerGlobal import taskMgr
from panda3d.core import Datagram, DatagramIterator
from panda3d.direct import DCClass


class ArdosClientRepository(ClientRepositoryBase):
    """
    The Ardos implementation of a clients repository for
    communication with an Ardos ClientAgent.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory("ArdosClientRepository")

    # This is required by DoCollectionManager.
    # It's the "root" distributed object generated at the top of the network tree.
    GameGlobalsId = 0

    def __init__(self, *args, **kwargs):
        ClientRepositoryBase.__init__(self, *args, **kwargs)

        if not self.GameGlobalsId:
            self.notify.error(f"GameGlobalsId must be defined!")

    @staticmethod
    def getConnectedEvent():
        return "ArdosClientRepository:Connected"

    @staticmethod
    def getDisconnectedEvent():
        return "ArdosClientRepository:Disconnected"

    @staticmethod
    def getHelloRespEvent():
        return "ArdosClientRepository:HelloResp"

    @staticmethod
    def getServerAddInterestEvent():
        return "ArdosClientRepository:ServerAddInterest"

    @staticmethod
    def getServerAddInterestMultipleEvent():
        return "ArdosClientRepository:ServerAddInterestMultiple"

    @staticmethod
    def getServerRemoveInterestEvent():
        return "ArdosClientRepository:ServerRemoveInterest"

    def handleDatagram(self, di: PyDatagramIterator) -> None:
        msgType = self.getMsgType()
        self.notify.warning(f"GOT MESSAGE: {msgType}")
        if msgType == CLIENT_HELLO_RESP:
            self.handleHelloResp()
        elif msgType == CLIENT_EJECT:
            self.handleGoGetLost(di)
        elif msgType == CLIENT_ENTER_OBJECT_REQUIRED:
            self.handleEnterObjectRequired(di)
        elif msgType == CLIENT_ENTER_OBJECT_REQUIRED_OTHER:
            self.handleEnterObjectRequiredOther(di)
        elif msgType == CLIENT_ENTER_OBJECT_REQUIRED_OWNER:
            self.handleEnterObjectRequiredOwner(di)
        elif msgType == CLIENT_ENTER_OBJECT_REQUIRED_OTHER_OWNER:
            self.handleEnterObjectRequiredOwnerOther(di)
        elif msgType == CLIENT_OBJECT_SET_FIELD:
            self.handleUpdateField(di)
        elif msgType == CLIENT_OBJECT_SET_FIELDS:
            self.handleUpdateFields(di)
        elif msgType in [CLIENT_OBJECT_LEAVING, CLIENT_OBJECT_LEAVING_OWNER]:
            self.handleObjectLeaving(di, msgType == CLIENT_OBJECT_LEAVING_OWNER)
        elif msgType == CLIENT_DONE_INTEREST_RESP:
            self.handleInterestDone(di)
        elif msgType == CLIENT_OBJECT_LOCATION:
            self.handleObjectLocation(di)
        elif msgType == CLIENT_ADD_INTEREST:
            self.handleServerAddInterest(di)
        elif msgType == CLIENT_ADD_INTEREST_MULTIPLE:
            self.handleServerAddInterestMultiple(di)
        elif msgType == CLIENT_REMOVE_INTEREST:
            self.handleServerRemoveInterest(di)
        else:
            self.notify.error(f"Got unknown message type {msgType}!")

        # If we're processing a lot of datagrams within one frame, we
        # may forget to send heartbeats.  Keep them coming!
        self.considerHeartbeat()

    def handleHelloResp(self) -> None:
        messenger.send(ArdosClientRepository.getHelloRespEvent(), [])

    def handleEnterObjectRequired(self, di: PyDatagramIterator) -> None:
        # Get the DO Id
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        assert parentId == self.GameGlobalsId or parentId in self.doId2do
        # Get the class Id
        classId = di.getUint16()

        # Look up the dclass
        dclass = self.dclassesByNumber[classId]

        dclass.startGenerate()
        # Create a new distributed object, and put it in the dictionary
        self.generateWithRequiredFields(dclass, doId, di, parentId, zoneId)
        dclass.stopGenerate()

    def handleEnterObjectRequiredOther(self, di: PyDatagramIterator) -> None:
        # Get the DO Id
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        # Get the class Id
        classId = di.getUint16()

        dclass = self.dclassesByNumber[classId]

        deferrable = getattr(dclass.getClassDef(), "deferrable", False)
        if not self.deferInterval or self.noDefer:
            deferrable = False

        now = globalClock.getFrameTime()
        if self.deferredGenerates or deferrable:
            # This object is deferrable, or there are already deferred
            # objects in the queue (so all objects have to be held
            # up).
            if self.deferredGenerates or now - self.lastGenerate < self.deferInterval:
                # Queue it for later.
                assert self.notify.debug(
                    f"deferring generate for {dclass.getName()} {doId}"
                )
                self.deferredGenerates.append(
                    (CLIENT_ENTER_OBJECT_REQUIRED_OTHER, doId)
                )

                # Keep a copy of the datagram, and move the di to the copy
                dg = Datagram(di.getDatagram())
                di = DatagramIterator(dg, di.getCurrentIndex())

                self.deferredDoIds[doId] = (
                    (parentId, zoneId, classId, doId, di),
                    deferrable,
                    dg,
                    [],
                )
                if len(self.deferredGenerates) == 1:
                    # We just deferred the first object on the queue;
                    # start the task to generate it.
                    taskMgr.remove("deferredGenerate")
                    taskMgr.doMethodLater(
                        self.deferInterval, self.doDeferredGenerate, "deferredGenerate"
                    )
            else:
                # We haven't generated any deferrable objects in a
                # while, so it's safe to go ahead and generate this
                # one immediately.
                self.lastGenerate = now
                self.doGenerate(parentId, zoneId, classId, doId, di)
        else:
            self.doGenerate(parentId, zoneId, classId, doId, di)

    def handleEnterObjectRequiredOwner(self, di: PyDatagramIterator) -> None:
        # Get the DO Id
        doId = di.getUint32()
        # parentId and zoneId are not relevant here
        parentId = di.getUint32()
        zoneId = di.getUint32()
        # Get the class Id
        classId = di.getUint16()
        # Look up the dclass
        dclass = self.dclassesByNumber[classId]
        dclass.startGenerate()
        # Create a new distributed object, and put it in the dictionary
        self.generateWithRequiredFieldsOwner(dclass, doId, di)
        dclass.stopGenerate()

    def handleEnterObjectRequiredOwnerOther(self, di: PyDatagramIterator) -> None:
        # Get the DO Id
        doId = di.getUint32()
        # parentId and zoneId are not relevant here
        parentId = di.getUint32()
        zoneId = di.getUint32()
        # Get the class Id
        classId = di.getUint16()
        # Look up the dclass
        dclass = self.dclassesByNumber[classId]
        dclass.startGenerate()
        # Create a new distributed object, and put it in the dictionary
        self.generateWithRequiredOtherFieldsOwner(dclass, doId, di)
        dclass.stopGenerate()

    def generateWithRequiredFieldsOwner(
        self, dclass: DCClass, doId: int, di: PyDatagramIterator
    ) -> None:
        if doId in self.doId2ownerView:
            # ...it is in our dictionary.
            # Just update it.
            self.notify.error(
                "duplicate owner generate for %s (%s)" % (doId, dclass.getName())
            )
            distObj = self.doId2ownerView[doId]
            assert distObj.dclass == dclass
            distObj.generate()
            distObj.updateRequiredFields(dclass, di)
            # updateRequiredFields calls announceGenerate
        elif self.cacheOwner.contains(doId):
            # ...it is in the cache.
            # Pull it out of the cache:
            distObj = self.cacheOwner.retrieve(doId)
            assert distObj.dclass == dclass
            # put it in the dictionary:
            self.doId2ownerView[doId] = distObj
            # and update it.
            distObj.generate()
            distObj.updateRequiredFields(dclass, di)
            # updateRequiredFields calls announceGenerate
        else:
            # ...it is not in the dictionary or the cache.
            # Construct a new one
            classDef = dclass.getOwnerClassDef()
            if classDef == None:
                self.notify.error(
                    "Could not create an undefined %s object. Have you created an owner view?"
                    % (dclass.getName())
                )
            distObj = classDef(self)
            distObj.dclass = dclass
            # Assign it an Id
            distObj.doId = doId
            # Put the new do in the dictionary
            self.doId2ownerView[doId] = distObj
            # Update the required fields
            distObj.generateInit()  # Only called when constructed
            distObj.generate()
            distObj.updateRequiredFields(dclass, di)
            # updateRequiredFields calls announceGenerate
        return distObj

    def handleUpdateFields(self, di: PyDatagramIterator) -> None:
        # Get the DO Id
        doId = di.getUint32()

        fieldCount = di.getUint16()
        for i in range(fieldCount):
            ovUpdated = self.__doUpdateOwner(doId, di)

            if doId in self.deferredDoIds:
                # This object hasn't really been generated yet.  Sit on
                # the update.
                args, deferrable, dg0, updates = self.deferredDoIds[doId]

                # Keep a copy of the datagram, and move the di to the copy
                dg = Datagram(di.getDatagram())
                di = DatagramIterator(dg, di.getCurrentIndex())

                updates.append((dg, di))
            else:
                # This object has been fully generated.  It's OK to update.
                self.__doUpdate(doId, di, ovUpdated)

    def handleObjectLeaving(self, di: PyDatagramIterator, ownerView=False) -> None:
        # Get the DO Id
        doId = di.getUint32()
        if not self.isLocalId(doId):
            # disable it.  But we never disable our own objects.
            self.disableDoId(doId, ownerView)

    def handleInterestDone(self, di: PyDatagramIterator) -> None:
        # We just received this message from the server; decide if we
        # should handle it immediately.
        if self.deferredGenerates:
            # No, we'd better wait, since some generates have been
            # deferred.  Instead, we'll queue up the message and
            # handle it in sequence.

            # Make a copy of the dg and di.
            dg = Datagram(di.getDatagram())
            di = DatagramIterator(dg, di.getCurrentIndex())

            self.deferredGenerates.append((CLIENT_DONE_INTEREST_RESP, (dg, di)))
        else:
            # We can handle it immediately.
            self.handleInterestDoneMessage(di)

    def handleObjectLocation(self, di: PyDatagramIterator) -> None:
        # See handleInterestDoneMessage(), above.
        if self.deferredGenerates:
            dg = Datagram(di.getDatagram())
            di = DatagramIterator(dg, di.getCurrentIndex())
            di2 = DatagramIterator(dg, di.getCurrentIndex())
            doId = di2.getUint32()
            if doId in self.deferredDoIds:
                self.deferredDoIds[doId][3].append((CLIENT_OBJECT_LOCATION, (dg, di)))
            else:
                # if we don't have a deferred generate stored for this object, process it
                # immediately
                super().handleObjectLocation(di)
        else:
            super().handleObjectLocation(di)

    def replayDeferredGenerate(self, msgType: int, extra) -> None:
        """Override this to do something appropriate with deferred
        "generate" messages when they are replayed()."""

        if msgType == CLIENT_DONE_INTEREST_RESP:
            dg, di = extra
            self.handleInterestDoneMessage(di)
        elif msgType == CLIENT_OBJECT_LOCATION:
            dg, di = extra
            self.handleObjectLocation(di)
        else:
            super().replayDeferredGenerate(msgType, extra)

    def handleServerAddInterest(self, di: PyDatagramIterator) -> None:
        """
        This is a single interest that has been opened by the server.
        It's not tracked the same way as interests opened by the client, as the client doesn't "own" the interest.
        :param di:
        :return:
        """
        context = di.getUint32()
        interestId = di.getUint16()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        messenger.send(
            ArdosClientRepository.getServerAddInterestEvent(),
            [context, interestId, parentId, zoneId],
        )

    def handleServerAddInterestMultiple(self, di: PyDatagramIterator) -> None:
        """
        This is a single interest that has been opened by the server under multiple zones.
        It's not tracked the same way as interests opened by the client, as the client doesn't "own" the interest.
        :param di:
        :return:
        """
        context = di.getUint32()
        interestId = di.getUint16()
        parentId = di.getUint32()
        zoneIds = [di.getUint32() for _ in range(di.getUint16())]
        messenger.send(
            ArdosClientRepository.getServerAddInterestMultipleEvent(),
            [context, interestId, parentId, zoneIds],
        )

    def handleServerRemoveInterest(self, di: PyDatagramIterator) -> None:
        """
        A server controlled interest has been closed.
        :param di:
        :return:
        """
        context = di.getUint32()
        interestId = di.getUint16()
        messenger.send(
            ArdosClientRepository.getServerRemoveInterestEvent(), [context, interestId]
        )

    def sendHello(self, version: str) -> None:
        dg = PyDatagram()
        dg.addUint16(CLIENT_HELLO)
        dg.addUint32(self.getDcFile().getHash())
        dg.addString(version)
        self.send(dg)

    def sendHeartbeat(self) -> None:
        datagram = PyDatagram()
        # Add message type
        datagram.addUint16(CLIENT_HEARTBEAT)
        # Send it!
        self.send(datagram)
        self.lastHeartbeat = globalClock.getRealTime()
        # This is important enough to consider flushing immediately
        # (particularly if we haven't run readerPollTask recently).
        self.considerFlush()

    def sendDisconnect(self):
        if self.isConnected():
            # Tell the game server that we're going:
            datagram = PyDatagram()
            # Add message type
            datagram.addUint16(CLIENT_DISCONNECT)
            # Send the message
            self.send(datagram)
            self.notify.info("Sent disconnect message to server")
            self.disconnect()
        self.stopHeartbeat()

    def sendSetLocation(self, doId: int, parentId: int, zoneId: int) -> None:
        datagram = PyDatagram()
        datagram.addUint16(CLIENT_OBJECT_LOCATION)
        datagram.addUint32(doId)
        datagram.addUint32(parentId)
        datagram.addUint32(zoneId)
        self.send(datagram)

    def lostConnection(self) -> None:
        messenger.send(ArdosClientRepository.getDisconnectedEvent())

        self.resetInterestStateForConnectionLoss()
        # Stop sending heartbeats
        self.stopHeartbeat()

        # Stop trying to read the connection
        self.stopReaderPollTask()

    # snake_case aliases for camelCase functions.
    send_hello = sendHello
    send_heartbeat = sendHeartbeat
    send_disconnect = sendDisconnect
    send_set_location = sendSetLocation
