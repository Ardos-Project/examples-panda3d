from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed.MsgTypes import *

from openworld.distributed import OpenWorldGlobals
from openworld.distributed.DistributedPlayerUD import DistributedPlayerUD


class AuthMgrUD(DistributedObjectGlobalUD):

    def __init__(self, air):
        DistributedObjectGlobalUD.__init__(self, air)

        self.air = air

    def login(self, username):
        """
        A client is requesting to authenticate with the server.
        :param username:
        :return:
        """
        sender = self.air.getMsgSender()

        # Every client that connects will have a channel automatically allocated to them by Arods.
        # This channel is in 32-bit space, whereas channels themselves are 64-bit.
        # The convention for client channels is, once authed, to store their accountId in the hi 32 bits,
        # and their avatarId in the lo 32 bits.
        # This means that when we receive a message from an (authed) client,
        # we can determine both their avatar DoId and their accountId without requiring any lookups.

        # Of course some projects might not even have a concept of an accountId or avatarId,
        # so this is just a convention you *can* use.
        # It's important to remember however that channels *have* to be globally unique across the cluster.

        # We're checking here to make sure the hi 32 bits of the client channel are 0.
        # If they're not, we've already authed this client and set their accountId.
        if sender >> 32:
            return

        # First things first, lets allocate a new DoId for this player.
        avatarId = self.air.allocateChannel()

        # Next, we'll open up two channels for them to start listening to.
        # Note that this is redundent, as we don't use accountId's here.
        # We can't just open the avatarId as a channel for them, as that's the avatar Distributed Object itself.
        # What we do instead is compute a unique channel based on the avatarId/accountId.

        # The avatar channel:
        datagram = PyDatagram()
        datagram.addServerHeader(sender, self.air.ourChannel, CLIENTAGENT_OPEN_CHANNEL)
        datagram.addChannel(self.GetPuppetConnectionChannel(avatarId))
        self.air.send(datagram)

        # The account channel:
        datagram = PyDatagram()
        datagram.addServerHeader(sender, self.air.ourChannel, CLIENTAGENT_OPEN_CHANNEL)
        datagram.addChannel(self.GetAccountConnectionChannel(avatarId))
        self.air.send(datagram)

        # You could now send a message to this connected client by using
        # either one of those computed channels.
        # E.g. to disconnect this client:
        # self.air.eject(
        #     self.GetPuppetConnectionChannel(avatarId), 100, "You've been disconnected!"
        # )

        # Next, we'll set their sender channel to be that of their avatarId.
        # Because we don't have a concept of an account here, we'll just set both the hi/lo as the avatarId.
        dg = PyDatagram()
        dg.addServerHeader(sender, self.air.ourChannel, CLIENTAGENT_SET_CLIENT_ID)
        dg.addChannel(avatarId << 32 | avatarId)
        self.air.send(dg)

        # Lets mark them as authenticated now.
        # This lets them send updates to any distributed object field marked `clsend`, not just anonymous uberdogs.
        # 2 = ESTABLISHED.
        self.air.setClientState(self.GetPuppetConnectionChannel(avatarId), 2)

        # Next, lets generate them a player object and set its location to (0, 0).
        # This is considered a non-existent location by the cluster.
        # I.e. The object exists, but isn't placed anywhere just yet.
        player = DistributedPlayerUD(self.air)
        player.setName(username)
        player.generateWithRequiredAndId(avatarId, 0, 0)

        # Next, we'll grant them ownership of their player.
        # This will let the client send fields marked `ownsend`.
        self.air.setOwner(avatarId, avatarId << 32 | avatarId)

        # Session objects are objects that lifetime is bound to the client and vice-versa.
        # If the clients DistributedPlayer were to be deleted from the state server, they'd be disconnected.
        # Likewise, if the player disconnects, their DistributedPlayer is automatically deleted.
        self.air.clientAddSessionObject(
            self.GetPuppetConnectionChannel(avatarId), avatarId
        )

        # Lastly, the client needs a way of knowing which districts (AI servers) are available to be played on.
        # We enable this behavior by generating a `DistributedDistrict` object in
        # a "well known" zoneId when an AI server comes online.
        # What we're doing below is opening a new interest for the client in this zone, which will cause
        # those DistributedDistrict objects to start getting generated on the client.
        # The client will then be able to pick which one they like and request to join.
        # See DistributedDistrictAI for the logic of moving a players avatar underneath them.
        self.air.clientAddInterest(
            self.GetPuppetConnectionChannel(avatarId),
            OpenWorldGlobals.INTEREST_HANDLE_CLIENT_DISTRICTS,
            self.air.getGameDoId(),
            OpenWorldGlobals.ZONE_ID_DISTRICTS,
        )
