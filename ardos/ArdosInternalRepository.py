from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from panda3d.core import URLSpec, UniqueIdAllocator
from panda3d.direct import DCPacker
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ConnectionRepository import ConnectionRepository
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from direct.distributed.MsgTypes import *
from direct.showbase import DConfig as config
from direct.showbase.MessengerGlobal import messenger
from direct.task.TaskManagerGlobal import taskMgr

from ardos.ArdosDatabaseInterface import ArdosDatabaseInterface
from ardos.NetMessenger import NetMessenger


class ArdosInternalRepository(ConnectionRepository):
    """
    This class is part of Panda3D's new MMO networking framework.
    It interfaces with an Ardos (https://github.com/Ardos/Ardos) server in
    order to manipulate objects in the Ardos cluster. It does not require any
    specific "gateway" into the Ardos network. Rather, it just connects directly
    to any Message Director. Hence, it is an "internal" repository.

    This class is suitable for constructing your own AI Servers and UberDOG servers
    using Panda3D. Objects with a "self.air" attribute are referring to an instance
    of this class.
    """

    notify = DirectNotifyGlobal.directNotify.newCategory("ArdosInternalRepository")

    def __init__(
        self,
        baseChannel,
        serverId=None,
        dcFileNames=None,
        dcSuffix="AI",
        connectMethod=None,
        threadedNet=None,
    ):
        if connectMethod is None:
            connectMethod = self.CM_NATIVE
        ConnectionRepository.__init__(
            self, connectMethod, config, hasOwnerView=False, threadedNet=threadedNet
        )
        self.setClientDatagram(False)
        self.dcSuffix = dcSuffix
        if hasattr(self, "setVerbose"):
            if self.config.GetBool("verbose-internalrepository"):
                self.setVerbose(1)

        # The State Server we are configured to use for creating objects.
        # If this is None, generating objects is not possible.
        self.serverId = self.config.GetInt("air-stateserver", 0) or None
        if serverId is not None:
            self.serverId = serverId

        maxChannels = self.config.GetInt("air-channel-allocation", 1000000)
        self.channelAllocator = UniqueIdAllocator(
            baseChannel, baseChannel + maxChannels - 1
        )
        self._registeredChannels = set()

        self.__contextCounter = 0

        self.netMessenger = NetMessenger(self)

        self.dbInterface = ArdosDatabaseInterface(self)
        self.__callbacks = {}
        self.__dclasses = {}

        self.ourChannel = self.allocateChannel()

        self.readDCFile(dcFileNames)

    def getContext(self):
        self.__contextCounter = (self.__contextCounter + 1) & 0xFFFFFFFF
        return self.__contextCounter

    def allocateChannel(self):
        """
        Allocate an unused channel out of this AIR's configured channel space.
        This is also used to allocate IDs for DistributedObjects, since those
        occupy a channel.
        """

        return self.channelAllocator.allocate()

    def deallocateChannel(self, channel):
        """
        Return the previously-allocated channel back to the allocation pool.
        """

        self.channelAllocator.free(channel)

    def registerForChannel(self, channel):
        """
        Register for messages on a specific Message Director channel.
        If the channel is already open by this AIR, nothing will happen.
        """

        if channel in self._registeredChannels:
            return
        self._registeredChannels.add(channel)

        dg = PyDatagram()
        dg.addServerControlHeader(CONTROL_ADD_CHANNEL)
        dg.addChannel(channel)
        self.send(dg)

    def unregisterForChannel(self, channel):
        """
        Unregister a channel subscription on the Message Director. The Message
        Director will cease to relay messages to this AIR sent on the channel.
        """

        if channel not in self._registeredChannels:
            return
        self._registeredChannels.remove(channel)

        dg = PyDatagram()
        dg.addServerControlHeader(CONTROL_REMOVE_CHANNEL)
        dg.addChannel(channel)
        self.send(dg)

    def addPostRemove(self, dg):
        """
        Register a datagram with the Message Director that gets sent out if the
        connection is ever lost.
        This is useful for registering cleanup messages: If the Panda3D process
        ever crashes unexpectedly, the Message Director will detect the socket
        close and automatically process any post-remove datagrams.
        """

        dg2 = PyDatagram()
        dg2.addServerControlHeader(CONTROL_ADD_POST_REMOVE)
        dg2.addUint64(self.ourChannel)
        dg2.addBlob(dg.getMessage())
        self.send(dg2)

    def clearPostRemove(self):
        """
        Clear all datagrams registered with addPostRemove.
        This is useful if the Panda3D process is performing a clean exit. It may
        clear the "emergency clean-up" post-remove messages and perform a normal
        exit-time clean-up instead, depending on the specific design of the game.
        """

        dg = PyDatagram()
        dg.addServerControlHeader(CONTROL_CLEAR_POST_REMOVES)
        dg.addUint64(self.ourChannel)
        self.send(dg)

    def setConName(self, name):
        """
        Set the connection name for this MD client displayed in Ardos logs.
        :param name:
        :return:
        """
        # TODO: Remove once added to Panda MsgTypes.
        CONTROL_SET_CON_NAME = 9012

        dg = PyDatagram()
        dg.addServerControlHeader(CONTROL_SET_CON_NAME)
        dg.addString(name)
        self.send(dg)

    def handleDatagram(self, di):
        msgType = self.getMsgType()

        if msgType in (
            STATESERVER_OBJECT_ENTER_AI_WITH_REQUIRED,
            STATESERVER_OBJECT_ENTER_AI_WITH_REQUIRED_OTHER,
        ):
            self.handleObjEntry(
                di, msgType == STATESERVER_OBJECT_ENTER_AI_WITH_REQUIRED_OTHER
            )
        elif msgType in (STATESERVER_OBJECT_CHANGING_AI, STATESERVER_OBJECT_DELETE_RAM):
            self.handleObjExit(di)
        elif msgType == STATESERVER_OBJECT_CHANGING_LOCATION:
            self.handleObjLocation(di)
        elif msgType in (
            DBSERVER_CREATE_OBJECT_RESP,
            DBSERVER_OBJECT_GET_ALL_RESP,
            DBSERVER_OBJECT_GET_FIELDS_RESP,
            DBSERVER_OBJECT_GET_FIELD_RESP,
            DBSERVER_OBJECT_SET_FIELD_IF_EQUALS_RESP,
            DBSERVER_OBJECT_SET_FIELDS_IF_EQUALS_RESP,
        ):
            self.dbInterface.handleDatagram(msgType, di)
        elif msgType == DBSS_OBJECT_GET_ACTIVATED_RESP:
            self.handleGetActivatedResp(di)
        elif msgType == STATESERVER_OBJECT_GET_LOCATION_RESP:
            self.handleGetLocationResp(di)
        elif msgType == STATESERVER_OBJECT_GET_ALL_RESP:
            self.handleGetObjectResp(di)
        elif msgType in (
            STATESERVER_OBJECT_GET_FIELD_RESP,
            STATESERVER_OBJECT_GET_FIELDS_RESP,
        ):
            self.handleGetObjectFieldsResp(
                di, msgType == STATESERVER_OBJECT_GET_FIELDS_RESP
            )
        elif msgType == CLIENTAGENT_GET_NETWORK_ADDRESS_RESP:
            self.handleGetNetworkAddressResp(di)
        # elif msgType == CLIENTAGENT_DONE_INTEREST_RESP:
        #    self.handleClientAgentInterestDoneResp(di)
        elif msgType >= 20000:
            # These messages belong to the NetMessenger:
            self.netMessenger.handle(msgType, di)
        else:
            self.notify.warning("Received message with unknown MsgType=%d" % msgType)

    def handleObjLocation(self, di):
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()

        do = self.doId2do.get(doId)

        if not do:
            self.notify.warning("Received location for unknown doId=%d!" % (doId))
            return

        do.setLocation(parentId, zoneId)

    def handleObjEntry(self, di, other):
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        classId = di.getUint16()

        if classId not in self.dclassesByNumber:
            self.notify.warning(
                "Received entry for unknown dclass=%d! (Object %d)" % (classId, doId)
            )
            return

        if doId in self.doId2do:
            return  # We already know about this object; ignore the entry.

        dclass = self.dclassesByNumber[classId]

        do = dclass.getClassDef()(self)
        do.dclass = dclass
        do.doId = doId
        # The DO came in off the server, so we do not unregister the channel when
        # it dies:
        do.doNotDeallocateChannel = True
        self.addDOToTables(do, location=(parentId, zoneId))

        # Now for generation:
        do.generate()
        if other:
            do.updateAllRequiredOtherFields(dclass, di)
        else:
            do.updateAllRequiredFields(dclass, di)

    def handleObjExit(self, di):
        doId = di.getUint32()

        if doId not in self.doId2do:
            self.notify.warning("Received AI exit for unknown object %d" % (doId))
            return

        do = self.doId2do[doId]
        self.removeDOFromTables(do)
        do.delete()
        do.sendDeleteEvent()

    def handleGetActivatedResp(self, di):
        ctx = di.getUint32()
        doId = di.getUint32()
        activated = di.getUint8()

        if ctx not in self.__callbacks:
            self.notify.warning(
                "Received unexpected DBSS_OBJECT_GET_ACTIVATED_RESP (ctx: %d)" % ctx
            )
            return

        try:
            self.__callbacks[ctx](doId, activated)
        finally:
            del self.__callbacks[ctx]

    def getActivated(self, doId, callback):
        ctx = self.getContext()
        self.__callbacks[ctx] = callback

        dg = PyDatagram()
        dg.addServerHeader(doId, self.ourChannel, DBSS_OBJECT_GET_ACTIVATED)
        dg.addUint32(ctx)
        dg.addUint32(doId)
        self.send(dg)

    def getLocation(self, doId, callback):
        """
        Ask a DistributedObject where it is.
        You should already be sure the object actually exists, otherwise the
        callback will never be called.
        Callback is called as: callback(doId, parentId, zoneId)
        """

        ctx = self.getContext()
        self.__callbacks[ctx] = callback
        dg = PyDatagram()
        dg.addServerHeader(doId, self.ourChannel, STATESERVER_OBJECT_GET_LOCATION)
        dg.addUint32(ctx)
        self.send(dg)

    def handleGetLocationResp(self, di):
        ctx = di.getUint32()
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()

        if ctx not in self.__callbacks:
            self.notify.warning(
                "Received unexpected STATESERVER_OBJECT_GET_LOCATION_RESP (ctx: %d)"
                % ctx
            )
            return

        try:
            self.__callbacks[ctx](doId, parentId, zoneId)
        finally:
            del self.__callbacks[ctx]

    def getObjectFields(self, doId, dclass, fields, callback):
        """
        Request the current field(s) values of a distributed object.
        You should already be sure the object actually exists, otherwise the
        callback will never be called.
        Callback is called as: callback(doId, fields)
        :param doId:
        :param dclass:
        :param fields:
        :param callback:
        :return:
        """
        if not fields:
            self.notify.error(
                f"Get object fields(s) request for {dclass.getName()} has empty fields"
            )
            return

        ctx = self.getContext()
        self.__callbacks[ctx] = callback
        self.__dclasses[ctx] = dclass

        dg = PyDatagram()
        dg.addServerHeader(
            doId,
            self.ourChannel,
            (
                STATESERVER_OBJECT_GET_FIELDS
                if len(fields) > 1
                else STATESERVER_OBJECT_GET_FIELD
            ),
        )
        dg.addUint32(ctx)
        dg.addUint32(doId)
        if len(fields) > 1:
            dg.addUint16(len(fields))

        for fieldName in fields:
            field = dclass.getFieldByName(fieldName)
            if not field:
                self.notify.error(
                    f"Get object field(s) request for {dclass.getName()} object contains invalid field named {fieldName}"
                )

            dg.addUint16(field.getNumber())

        self.send(dg)

    def handleGetObjectFieldsResp(self, di, multi):
        doId = self.getMsgSender()
        ctx = di.getUint32()
        success = di.getBool()

        if ctx not in self.__callbacks or ctx not in self.__dclasses:
            self.notify.warning(
                "Received unexpected STATESERVER_OBJECT_GET_FIELD(S)_RESP (ctx: %d)"
                % ctx
            )
            return

        if not success:
            try:
                self.__callbacks[ctx](doId, None)
                return
            finally:
                del self.__callbacks[ctx]
                del self.__dclasses[ctx]

        if multi:
            fieldCount = di.getUint16()
        else:
            fieldCount = 1

        fields = {}
        unpacker = DCPacker()
        unpacker.setUnpackData(di.getRemainingBytes())
        for x in range(fieldCount):
            fieldId = unpacker.rawUnpackInt16()
            field = self.__dclasses[ctx].getFieldByIndex(fieldId)

            if not field:
                self.notify.error(
                    f"Received bad field {fieldId} in getObjectFields for dclass {self.__dclasses[ctx].getName()}"
                )

            unpacker.beginUnpack(field)
            fields[field.getName()] = field.unpackArgs(unpacker)
            unpacker.endUnpack()

        try:
            self.__callbacks[ctx](doId, fields)
        finally:
            del self.__callbacks[ctx]
            del self.__dclasses[ctx]

    def getObject(self, doId, callback):
        """
        Get the entire state of an object.
        You should already be sure the object actually exists, otherwise the
        callback will never be called.
        Callback is called as: callback(doId, parentId, zoneId, dclass, fields)
        """

        ctx = self.getContext()
        self.__callbacks[ctx] = callback
        dg = PyDatagram()
        dg.addServerHeader(doId, self.ourChannel, STATESERVER_OBJECT_GET_ALL)
        dg.addUint32(ctx)
        dg.addUint32(doId)
        self.send(dg)

    def handleGetObjectResp(self, di):
        ctx = di.getUint32()
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        classId = di.getUint16()

        if ctx not in self.__callbacks:
            self.notify.warning(
                "Received unexpected STATESERVER_OBJECT_GET_ALL_RESP (ctx: %d)" % ctx
            )
            return

        if classId not in self.dclassesByNumber:
            self.notify.warning(
                "Received STATESERVER_OBJECT_GET_ALL_RESP for unknown dclass=%d! (Object %d)"
                % (classId, doId)
            )
            return

        dclass = self.dclassesByNumber[classId]

        fields = {}
        unpacker = DCPacker()
        unpacker.setUnpackData(di.getRemainingBytes())

        # Required:
        for i in range(dclass.getNumInheritedFields()):
            field = dclass.getInheritedField(i)
            if not field.isRequired() or field.asMolecularField():
                continue
            unpacker.beginUnpack(field)
            fields[field.getName()] = field.unpackArgs(unpacker)
            unpacker.endUnpack()

        # Other:
        other = unpacker.rawUnpackUint16()
        for i in range(other):
            field = dclass.getFieldByIndex(unpacker.rawUnpackUint16())
            unpacker.beginUnpack(field)
            fields[field.getName()] = field.unpackArgs(unpacker)
            unpacker.endUnpack()

        try:
            self.__callbacks[ctx](doId, parentId, zoneId, dclass, fields)
        finally:
            del self.__callbacks[ctx]

    def getNetworkAddress(self, clientId, callback):
        """
        Get the endpoints of a client connection.
        You should already be sure the client actually exists, otherwise the
        callback will never be called.
        Callback is called as: callback(remoteIp, remotePort, localIp, localPort)
        """

        ctx = self.getContext()
        self.__callbacks[ctx] = callback
        dg = PyDatagram()
        dg.addServerHeader(clientId, self.ourChannel, CLIENTAGENT_GET_NETWORK_ADDRESS)
        dg.addUint32(ctx)
        self.send(dg)

    def handleGetNetworkAddressResp(self, di):
        ctx = di.getUint32()
        remoteIp = di.getString()
        remotePort = di.getUint16()
        localIp = di.getString()
        localPort = di.getUint16()

        if ctx not in self.__callbacks:
            self.notify.warning(
                "Received unexpected CLIENTAGENT_GET_NETWORK_ADDRESS_RESP (ctx: %d)"
                % ctx
            )
            return

        try:
            self.__callbacks[ctx](remoteIp, remotePort, localIp, localPort)
        finally:
            del self.__callbacks[ctx]

    def sendUpdate(self, do, fieldName, args):
        """
        Send a field update for the given object.
        You should use do.sendUpdate(...) instead. This is not meant to be
        called directly unless you really know what you are doing.
        """

        self.sendUpdateToChannel(do, do.doId, fieldName, args)

    def sendUpdateToChannel(self, do, channelId, fieldName, args):
        """
        Send an object field update to a specific channel.
        This is useful for directing the update to a specific client or node,
        rather than at the State Server managing the object.
        You should use do.sendUpdateToChannel(...) instead. This is not meant
        to be called directly unless you really know what you are doing.
        """

        dclass = do.dclass
        field = dclass.getFieldByName(fieldName)
        dg = field.aiFormatUpdate(do.doId, channelId, self.ourChannel, args)
        self.send(dg)

    def sendUpdateToChannelFrom(self, do, channelId, fieldName, fromId, args):
        """
        Send an object field update to a specific channel while impersonating the sender channel.
        This is useful for directing the update to a specific client or node,
        rather than at the State Server managing the object.
        You should use do.sendUpdateToChannel(...) instead. This is not meant
        to be called directly unless you really know what you are doing.
        """

        dclass = do.dclass
        field = dclass.getFieldByName(fieldName)
        dg = field.aiFormatUpdate(do.doId, channelId, fromId, args)
        self.send(dg)

    def sendUpdateToUD(self, dclassName, fieldName, doId, args):
        """
        Used for sending messages from an AI -> UD
        :param dclassName:
        :param fieldName:
        :param doId:
        :param args:
        :return:
        """
        dclass = self.dclassesByName.get(dclassName)
        assert dclass, "dclass %s not found in DC files" % dclassName
        dg = dclass.aiFormatUpdate(fieldName, doId, doId, self.ourChannel, args)
        self.send(dg)

    def sendUpdateToUDFrom(self, dclassName, fieldName, doId, fromId, args):
        """
        Used for sending messages from an AI -> UD while impersonating the sender channel.
        :param dclassName:
        :param fieldName:
        :param doId:
        :param fromId:
        :param args:
        :return:
        """
        dclass = self.dclassesByName.get(dclassName)
        assert dclass, "dclass %s not found in DC files" % dclassName
        dg = dclass.aiFormatUpdate(fieldName, doId, doId, fromId, args)
        self.send(dg)

    def sendUpdateToAI(self, dclassName, fieldName, doId, channel, args, sender=None):
        """
        Used for sending messages from an UD -> AI
        :param sender:
        :param dclassName:
        :param fieldName:
        :param doId:
        :param channel:
        :param args:
        :return:
        """
        dclass = self.dclassesByName.get(dclassName)
        assert dclass, "dclass %s not found in DC files" % dclassName
        dg = dclass.aiFormatUpdate(
            fieldName, doId, channel, sender or self.ourChannel, args
        )
        self.send(dg)

    def sendActivate(self, doId, parentId, zoneId, dclass=None, fields=None):
        """
        Activate a DBSS object, given its doId, into the specified parentId/zoneId.
        If both dclass and fields are specified, an ACTIVATE_WITH_DEFAULTS_OTHER
        will be sent instead. In other words, the specified fields will be
        auto-applied during the activation.
        """

        fieldPacker = DCPacker()
        fieldCount = 0
        if dclass and fields:
            for k, v in fields.items():
                field = dclass.getFieldByName(k)
                if not field:
                    self.notify.error(
                        "Activation request for %s object contains "
                        "invalid field named %s" % (dclass.getName(), k)
                    )

                fieldPacker.rawPackUint16(field.getNumber())
                fieldPacker.beginPack(field)
                field.packArgs(fieldPacker, v)
                fieldPacker.endPack()
                fieldCount += 1

            dg = PyDatagram()
            dg.addServerHeader(
                doId, self.ourChannel, DBSS_OBJECT_ACTIVATE_WITH_DEFAULTS_OTHER
            )
            dg.addUint32(doId)
            dg.addUint32(parentId)
            dg.addUint32(zoneId)
            dg.addUint16(dclass.getNumber())
            dg.addUint16(fieldCount)
            dg.appendData(fieldPacker.getBytes())
            self.send(dg)
        else:
            dg = PyDatagram()
            dg.addServerHeader(
                doId, self.ourChannel, DBSS_OBJECT_ACTIVATE_WITH_DEFAULTS
            )
            dg.addUint32(doId)
            dg.addUint32(parentId)
            dg.addUint32(zoneId)
            self.send(dg)

    def sendSetLocation(self, do, parentId, zoneId):
        dg = PyDatagram()
        dg.addServerHeader(do.doId, self.ourChannel, STATESERVER_OBJECT_SET_LOCATION)
        dg.addUint32(parentId)
        dg.addUint32(zoneId)
        self.send(dg)

    def generateWithRequired(self, do, parentId, zoneId, optionalFields=[]):
        """
        Generate an object onto the State Server, choosing an ID from the pool.
        You should use do.generateWithRequired(...) instead. This is not meant
        to be called directly unless you really know what you are doing.
        """

        doId = self.allocateChannel()
        self.generateWithRequiredAndId(do, doId, parentId, zoneId, optionalFields)

    def generateWithRequiredAndId(self, do, doId, parentId, zoneId, optionalFields=[]):
        """
        Generate an object onto the State Server, specifying its ID and location.
        You should use do.generateWithRequiredAndId(...) instead. This is not
        meant to be called directly unless you really know what you are doing.
        """

        do.doId = doId
        self.addDOToTables(do, location=(parentId, zoneId))
        do.sendGenerateWithRequired(self, parentId, zoneId, optionalFields)

    def requestDelete(self, do):
        """
        Request the deletion of an object that already exists on the State Server.
        You should use do.requestDelete() instead. This is not meant to be
        called directly unless you really know what you are doing.
        """

        dg = PyDatagram()
        dg.addServerHeader(do.doId, self.ourChannel, STATESERVER_OBJECT_DELETE_RAM)
        dg.addUint32(do.doId)
        self.send(dg)

    def connect(self, host, port=7199):
        """
        Connect to a Message Director. The airConnected message is sent upon
        success.
        N.B. This overrides the base class's connect(). You cannot use the
        ConnectionRepository connect() parameters.
        """

        url = URLSpec()
        url.setServer(host)
        url.setPort(port)

        self.notify.info("Now connecting to %s:%s..." % (host, port))
        ConnectionRepository.connect(
            self,
            [url],
            successCallback=self.__connected,
            failureCallback=self.__connectFailed,
            failureArgs=[host, port],
        )

    def __connected(self):
        self.notify.info("Connected successfully.")

        # Listen to our channel...
        self.registerForChannel(self.ourChannel)

        # If we're configured with a State Server, register a post-remove to
        # clean up whatever objects we own on this server should we unexpectedly
        # fall over and die.
        if self.serverId:
            dg = PyDatagram()
            dg.addServerHeader(
                self.serverId, self.ourChannel, STATESERVER_DELETE_AI_OBJECTS
            )
            dg.addChannel(self.ourChannel)
            self.addPostRemove(dg)

        messenger.send("airConnected")
        self.handleConnected()

    def __connectFailed(self, code, explanation, host, port):
        self.notify.warning("Failed to connect! (code=%s; %r)" % (code, explanation))

        # Try again...
        retryInterval = config.GetFloat("air-reconnect-delay", 5.0)
        taskMgr.doMethodLater(
            retryInterval, self.connect, "Reconnect delay", extraArgs=[host, port]
        )

    def handleConnected(self):
        """
        Subclasses should override this if they wish to handle the connection
        event.
        """

    def lostConnection(self):
        # This should be overridden by a subclass if unexpectedly losing connection
        # is okay.
        self.notify.error("Lost connection to gameserver!")

    def writeServerEvent(self, eventType, *args, **kwargs):
        """
        Generic function for writing game events, telemetry, etc., to a logging source.
        Historically there was a dedicated "Event Logger" role as part of the OTP server,
        however it's now up to the application to define its own logging system.
        Example: writeServerEvent('suspicious', avId=avId, issue='Player did something suspicious!')
        """
        # Inheritors to override.
        self.notify.warning(f"writeServerEvent not defined!")

    def setAI(self, doId, aiChannel):
        """
        Sets the AI of the specified DistributedObjectAI to be the specified channel.
        Generally, you should not call this method, and instead call DistributedObjectAI.setAI.
        """

        dg = PyDatagram()
        dg.addServerHeader(doId, aiChannel, STATESERVER_OBJECT_SET_AI)
        dg.addUint64(aiChannel)
        self.send(dg)

    def eject(self, clientChannel, reasonCode, reason):
        """
        Kicks the client residing at the specified clientChannel, using the specifed reasoning.
        """

        dg = PyDatagram()
        dg.addServerHeader(clientChannel, self.ourChannel, CLIENTAGENT_EJECT)
        dg.addUint16(reasonCode)
        dg.addString(reason)
        self.send(dg)

    def setClientState(self, clientChannel, state):
        """
        Sets the state of the client on the CA.
        Useful for logging in and logging out, and for little else.
        """

        dg = PyDatagram()
        dg.addServerHeader(clientChannel, self.ourChannel, CLIENTAGENT_SET_STATE)
        dg.addUint16(state)
        self.send(dg)

    def setAllowClientSend(self, do, channelId, fieldNameList=[]):
        """
        Overrides the security of a field(s) specified, allows an owner of a DistributedObject to send
        the field(s) regardless if its marked ownsend/clsend.
        """

        dg = PyDatagram()
        dg.addServerHeader(channelId, self.ourChannel, CLIENTAGENT_SET_FIELDS_SENDABLE)
        fieldIds = []
        for fieldName in fieldNameList:
            field = do.dclass.getFieldByName(fieldName)

            if not field:
                continue

            fieldIds.append(field.getNumber())

        dg.addUint32(do.doId)
        dg.addUint16(len(fieldIds))
        for fieldId in fieldIds:
            dg.addUint16(fieldId)

        self.send(dg)

    def clientAddSessionObject(self, clientChannel, doId):
        """
        Declares the specified DistributedObject to be a "session object",
        meaning that it is destroyed when the client disconnects.
        Generally used for avatars owned by the client.
        """

        dg = PyDatagram()
        dg.addServerHeader(
            clientChannel, self.ourChannel, CLIENTAGENT_ADD_SESSION_OBJECT
        )
        dg.addUint32(doId)
        self.send(dg)

    def clientRemoveSessionObject(self, clientChannel, doId):
        """
        Removes a previously added session object from the client.
        :param clientChannel:
        :param doId:
        :return:
        """

        dg = PyDatagram()
        dg.addServerHeader(
            clientChannel, self.ourChannel, CLIENTAGENT_REMOVE_SESSION_OBJECT
        )
        dg.addUint32(doId)
        self.send(dg)

    def clientAddInterest(
        self,
        client_channel: int,
        interest_id: int,
        parent_id: int,
        zone_id: int,
        callback: object = None,
    ) -> None:
        """
        Opens an interest on the behalf of the client. This, used in conjunction
        with add_interest: visible (or preferably, disabled altogether), will mitigate
        possible security risks.
        """

        dg = PyDatagram()
        dg.addServerHeader(client_channel, self.ourChannel, CLIENTAGENT_ADD_INTEREST)
        dg.addUint16(interest_id)
        dg.addUint32(parent_id)
        dg.addUint32(zone_id)
        self.send(dg)

        if callback != None:
            ctx = (client_channel, interest_id)
            self.__callbacks[ctx] = callback

    def client_add_interest_multiple(
        self,
        client_channel: int,
        interest_id: int,
        parent_id: int,
        zone_list: int,
        callback: object = None,
    ) -> None:
        """ """

        dg = PyDatagram()
        dg.addServerHeader(
            client_channel, self.ourChannel, CLIENTAGENT_ADD_INTEREST_MULTIPLE
        )
        dg.addUint16(interest_id)
        dg.addUint32(parent_id)
        dg.addUint16(len(zone_list))
        for zoneId in zone_list:
            dg.addUint32(zoneId)

        if callback != None:
            ctx = (client_channel, interest_id)
            self.__callbacks[ctx] = callback

        self.send(dg)

    def client_remove_interest(
        self, client_channel: int, interest_id: int, callback: object = None
    ) -> None:
        """ """

        dg = PyDatagram()
        dg.addServerHeader(client_channel, self.ourChannel, CLIENTAGENT_REMOVE_INTEREST)
        dg.addUint16(interest_id)
        self.send(dg)

        if callback != None:
            ctx = (client_channel, interest_id)
            self.__callbacks[ctx] = callback

    def handle_client_agent_interest_done_resp(self, di: PyDatagramIterator) -> None:
        """
        Sent by the ClientAgent to the caller of CLIENTAGENT_ADD_INTEREST to inform them that the interest operation has completed.
        """

        client_channel = di.getUint64()
        interest_id = di.getUint16()
        ctx = (client_channel, interest_id)

        if ctx not in self.__callbacks:
            self.notify.warning(
                "Received unexpected CLIENTAGENT_DONE_INTEREST_RESP (ctx: (%s, %s))"
                % ctx
            )
            return

        try:
            self.__callbacks[ctx](client_channel, interest_id)
        finally:
            del self.__callbacks[ctx]

    def setOwner(self, doId: int, newOwner: int) -> None:
        """
        Sets the owner of a DistributedObject. This will enable the new owner to send "ownsend" fields,
        and will generate an OwnerView.
        """

        dg = PyDatagram()
        dg.addServerHeader(doId, self.ourChannel, STATESERVER_OBJECT_SET_OWNER)
        dg.addUint64(newOwner)
        self.send(dg)

    set_owner = setOwner

    # Snake case helpers
    write_server_event = writeServerEvent
    set_ai = setAI
    set_client_state = setClientState
    client_add_session_object = clientAddSessionObject
