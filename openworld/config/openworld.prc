window-title Open World Example

# Server version (must match ardos.config.yml.)
server-version openworld

# Networking
collect-tcp #t
collect-tcp-interval 0.1
http-connect-timeout 20
http-timeout 30
dc-file openworld/config/openworld.dc
dc-file config/direct.dc

# Used to visualize the world grids.
visualize-cartesian-grid #t
