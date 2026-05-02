# This is the root Distributed Object ID for the networked tree.
# The actual ID isn't special, we've just gone with 4001 as a convention.
# Usually the low channel range (<2000) is reserved for cluster components.
# (Client Agents, State Servers, etc.)
ROOT_DO_ID = 4001

# 41xx are reserved for UberDOG DoId's.
# Again, just a convention.
AUTH_MGR_DO_ID = 4100

# The zoneId underneath ROOT_DO_ID that DistributedDistrict objects live in.
# This is used as a discovery mechanism primarily for clients to see which servers are online.
ZONE_ID_DISTRICTS = 1
# The zoneId underneath districts (AI servers) that the world is generated in.
ZONE_ID_WORLD = 1

# Note that it's possible (when enabled) to allow clients to set their own location/interests,
# although this is *not* recommended.
# Because of this, the below interest handles are actually (1 << 15) + X to signify they've been opened by the server
# and to avoid collisions with client opened interests.
# E.g. You could open an interest from a client *and* a server with an ID of 1, without having a collision.

# This is an interest that will be opened for the lifetime of a client.
# It lets the client know which districts (AI servers) are currently online.
# See AuthMgrUD.
INTEREST_HANDLE_CLIENT_DISTRICTS = 1
INTEREST_HANDLE_CLIENT_WORLD = 2
