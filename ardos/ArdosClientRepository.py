"""ArdosClientRepository module: contains the ArdosClientRepository class"""

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClientRepositoryBase import ClientRepositoryBase
from direct.distributed.DistributedObject import DistributedObject
from direct.distributed.MsgTypes import *
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.PyDatagramIterator import PyDatagramIterator
from panda3d.direct import DCClass


class ArdosClientRepository(ClientRepositoryBase):
    """
    The Ardos implementation of a clients repository for
    communication with an Ardos ClientAgent.

    This repo will emit events for:
    * CLIENT_HELLO_RESP
    * CLIENT_EJECT ( error_code, reason )
    * CLIENT_OBJECT_LEAVING ( do_id )
    * CLIENT_ADD_INTEREST ( context, interest_id, parent_id, zone_id )
    * CLIENT_ADD_INTEREST_MULTIPLE ( icontext, interest_id, parent_id, [zone_ids] )
    * CLIENT_REMOVE_INTEREST ( context, interest_id )
    * CLIENT_DONE_INTEREST_RESP ( context, interest_id )
    * LOST_CONNECTION ()
    """

    notify = DirectNotifyGlobal.directNotify.newCategory("ArdosClientRepository")

    # This is required by DoCollectionManager, even though it's not
    # used by this implementation.
    GameGlobalsId = 0

    def __init__(self, *args, **kwargs):
        ClientRepositoryBase.__init__(self, *args, **kwargs)
        base.finalExitCallbacks.append(self.shutdown)
        self.message_handlers = {CLIENT_HELLO_RESP: self.handleHelloResp,
                                 CLIENT_EJECT: self.handleEject,
                                 CLIENT_ENTER_OBJECT_REQUIRED: self.handleEnterObjectRequired,
                                 CLIENT_ENTER_OBJECT_REQUIRED_OWNER: self.handleEnterObjectRequiredOwner,
                                 CLIENT_OBJECT_SET_FIELD: self.handleUpdateField,
                                 CLIENT_OBJECT_SET_FIELDS: self.handleUpdateFields,
                                 CLIENT_OBJECT_LEAVING: self.handleObjectLeaving,
                                 CLIENT_OBJECT_LOCATION: self.handleObjectLocation,
                                 CLIENT_ADD_INTEREST: self.handleAddInterest,
                                 CLIENT_ADD_INTEREST_MULTIPLE: self.handleAddInterestMultiple,
                                 CLIENT_REMOVE_INTEREST: self.handleRemoveInterest,
                                 CLIENT_DONE_INTEREST_RESP: self.handleInterestDoneMessage,
                                 }

    def handleDatagram(self, di: PyDatagramIterator) -> None:
        msgType = self.getMsgType()
        if msgType in self.message_handlers:
            self.message_handlers[msgType](di)
        else:
            self.notify.error("Got unknown message type %d!" % (msgType,))

        self.considerHeartbeat()

    def handleHelloResp(self, di: PyDatagramIterator) -> None:
        messenger.send("CLIENT_HELLO_RESP", [])

    def handleEject(self, di: PyDatagramIterator) -> None:
        error_code = di.getUint16()
        reason = di.getString()
        messenger.send("CLIENT_EJECT", [error_code, reason])

    def handleEnterObjectRequired(self, di: PyDatagramIterator) -> None:
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        dclassId = di.getUint16()
        dclass = self.dclassesByNumber[dclassId]
        self.generateWithRequiredFields(dclass, doId, di, parentId, zoneId)

    def handleEnterObjectRequiredOwner(self, di: PyDatagramIterator) -> None:
        doId = di.getUint32()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        dclassId = di.getUint16()
        dclass = self.dclassesByNumber[dclassId]
        self.generateWithRequiredFieldsOwner(dclass, doId, di)

    def generateWithRequiredFieldsOwner(self, dclass: DCClass, doId: int, di: PyDatagramIterator) -> None:
        if doId in self.doId2ownerView:
            # ...it is in our dictionary.
            # Just update it.
            self.notify.error('duplicate owner generate for %s (%s)' % (
                doId, dclass.getName()))
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
                self.notify.error("Could not create an undefined %s object. Have you created an owner view?" % (dclass.getName()))
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
        # Can't test this without the server actually sending it.
        self.notify.error("CLIENT_OBJECT_SET_FIELDS not implemented!")
        # # Here's some tentative code and notes:
        # do_id = di.getUint32()
        # field_count = di.getUint16()
        # for i in range(0, field_count):
        #     field_id = di.getUint16()
        #     field = self.get_dc_file().get_field_by_index(field_id)
        #     # print(type(field))
        #     # print(field)
        #     # FIXME: Get field type, unpack value, create and send message.
        #     # value = di.get?()
        #     # Assemble new message

    def handleObjectLeaving(self, di: PyDatagramIterator) -> None:
        doId = di.getUint32()
        distObj = self.doId2do.get(doId)
        distObj.delete()
        self.deleteObject(doId)
        messenger.send("CLIENT_OBJECT_LEAVING", [doId])

    def handleAddInterest(self, di: PyDatagramIterator) -> None:
        context = di.getUint32()
        interestId = di.getUint16()
        parentId = di.getUint32()
        zoneId = di.getUint32()
        messenger.send("CLIENT_ADD_INTEREST", [context, interestId, parentId, zoneId])

    def handleAddInterestMultiple(self, di: PyDatagramIterator) -> None:
        context = di.getUint32()
        interestId = di.getUint16()
        parentId = di.getUint32()
        zoneIds = [di.getUint32() for i in range(0, di.getUint16())]
        messenger.send("CLIENT_ADD_INTEREST_MULTIPLE", [context, interestId, parentId, zoneIds])

    def handleRemoveInterest(self, di: PyDatagramIterator) -> None:
        context = di.getUint32()
        interestId = di.getUint16()
        messenger.send("CLIENT_REMOVE_INTEREST", [context, interestId])

    def deleteObject(self, doId: int) -> None:
        """
        implementation copied from ClientRepository.py

        Removes the object from the client's view of the world.  This
        should normally not be called directly except in the case of
        error recovery, since the server will normally be responsible
        for deleting and disabling objects as they go out of scope.

        After this is called, future updates by server on this object
        will be ignored (with a warning message).  The object will
        become valid again the next time the server sends a generate
        message for this doId.

        This is not a distributed message and does not delete the
        object on the server or on any other client.
        """
        if doId in self.doId2do:
            # If it is in the dictionary, remove it.
            obj = self.doId2do[doId]
            # Remove it from the dictionary
            del self.doId2do[doId]
            # Disable, announce, and delete the object itself...
            # unless delayDelete is on...
            obj.deleteOrDelay()
            if self.isLocalId(doId):
                self.freeDoId(doId)
        elif self.cache.contains(doId):
            # If it is in the cache, remove it.
            self.cache.delete(doId)
            if self.isLocalId(doId):
                self.freeDoId(doId)
        else:
            # Otherwise, ignore it
            self.notify.warning(
                "Asked to delete non-existent DistObj " + str(doId))

    def sendUpdate(self, distObj: DistributedObject, fieldName: str, args) -> None:
        """ Sends a normal update for a single field. """
        dg = distObj.dclass.clientFormatUpdate(
            fieldName, distObj.doId, args)
        self.send(dg)

    def sendHello(self, version: str) -> None:
        dg = PyDatagram()
        dg.addUint16(CLIENT_HELLO)
        dg.addUint32(self.getDcFile().getHash())
        dg.addUtring(version)
        self.send(dg)

    def sendHeartbeat(self) -> None:
        datagram = PyDatagram()
        datagram.addUint16(CLIENT_HEARTBEAT)
        self.send(datagram)

    def sendAddInterest(self, context: int, interestId: int, parentId: int, zoneId: int) -> None:
        dg = PyDatagram()
        dg.addUint16(CLIENT_ADD_INTEREST)
        dg.addUint32(context)
        dg.addUint16(interestId)
        dg.addUint32(parentId)
        dg.addUint32(zoneId)
        self.send(dg)

    def sendAddInterestMultiple(self, context: int, interestId: int, parentId: int, zoneIds) -> None:
        dg = PyDatagram()
        dg.addUint16(CLIENT_ADD_INTEREST_MULTIPLE)
        dg.addUint32(context)
        dg.addUint16(interestId)
        dg.addUint32(parentId)
        dg.addUint16(len(zoneIds))
        for zoneId in zoneIds:
            dg.addUint32(zoneId)
        self.send(dg)

    def sendRemoveInterest(self, context: int, interestId: int) -> None:
        dg = PyDatagram()
        dg.addUint16(CLIENT_REMOVE_INTEREST)
        dg.addUint32(context)
        dg.addUint16(interestId)
        self.send(dg)

    def lostConnection(self) -> None:
        messenger.send("LOST_CONNECTION")

    def disconnect(self) -> None:
        """
        This implicitly deletes all objects from the repository.
        """
        for doId in self.doId2do.keys():
            self.deleteObject(doId)

        ClientRepositoryBase.disconnect(self)