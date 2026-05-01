from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal


class AuthMgr(DistributedObjectGlobal):

    def login(self, username):
        self.sendUpdate("login", [username])
