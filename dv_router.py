"""Your awesome Distance Vector router for CS 168."""

import sim.api as api
import sim.basics as basics

# We define infinity as a distance of 16.
INFINITY = 16


class DVRouter(basics.DVRouterBase):
    # NO_LOG = True # Set to True on an instance to disable its logging
    # POISON_MODE = True # Can override POISON_MODE here
    # DEFAULT_TIMER_INTERVAL = 5 # Can override this yourself for testing

    def __init__(self):
        """
        Called when the instance is initialized.

        You probably want to do some additional initialization here.

        """
        self.router_table = {} # destination address => [port, latency, create time]
        self.port_latency = {} # port => link's latency (distance to destination)
        self.host_port = {} # host => port connected to
        self.poison = [] # when route expires, destinations to poison
        self.start_timer()  # Starts calling handle_timer() at correct rate

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this Entity goes up.

        The port attached to the link and the link latency are passed
        in.

        """
        self.port_latency[port] = latency
        for dest, info in self.router_table.items():
            if (info[0] != port):
                self.send(basics.RoutePacket(dest, info[1]), port)
            elif (info[0] == port and self.POISON_MODE):
                self.send(basics.RoutePacket(dest, INFINITY), port)

    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this Entity does down.

        The port number used by the link is passed in.

        """
        remove_hosts = []
        remove_dests = []
        for host in self.host_port:
            if (self.host_port[host] == port):
                remove_hosts.append(host)
        for host in remove_hosts:
            del self.host_port[host]
       
        for dest, info in self.router_table.items():
            if (port == info[0]):
                remove_dests.append(dest)
        # remove routes
        for dest in remove_dests:
            del self.router_table[dest]
            if self.POISON_MODE: 
                self.poison.append(dest)
            # add default host route
            self.host_route_default(dest, api.current_time())
        del self.port_latency[port]

    def host_route_default(self, dest, create_time):
        if dest in self.host_port:
            port = self.host_port[dest]
            if dest not in self.router_table:
                self.router_table[dest] = [port, self.port_latency[port], create_time]
            if self.port_latency[port] < self.router_table[dest][1]:
                self.router_table[dest] = [port, self.port_latency[port], create_time]

    def handle_rx(self, packet, port):
        """
        Called by the framework when this Entity receives a packet.

        packet is a Packet (or subclass).
        port is the port number it arrived on.

        You definitely want to fill this in.

        """
        #self.log("RX %s on %s (%s)", packet, port, api.current_time())
        if isinstance(packet, basics.RoutePacket):
            self.route_update(packet.destination, port, packet.latency)
        elif isinstance(packet, basics.HostDiscoveryPacket):
            self.host_port[packet.src] = port
            self.route_update(packet.src, port, 0)
        else:
            destination = packet.dst
            if destination in self.router_table:
                # No hairpin
                if (self.router_table[destination][0] != port): 
                    self.send(packet, self.router_table[destination][0])

    def route_update(self, destination, port, latency):
        if (latency + self.port_latency[port] < INFINITY):
            total_distance = latency + self.port_latency[port]
        else:
            total_distance = INFINITY

        if destination in self.router_table:
            # Destination in routing table
            if port == self.router_table[destination][0]:
                if total_distance != INFINITY:
                    # trust most recent route
                    self.router_table[destination] = [port, total_distance, api.current_time()]
                else: 
                    if destination in self.router_table:
                        del self.router_table[destination]
                        if self.POISON_MODE: 
                            self.poison.append(destination)
            elif (port != self.router_table[destination][0] and total_distance <= self.router_table[destination][1]):
                self.router_table[destination] = [port, total_distance, api.current_time()]
        else: 
            if total_distance != INFINITY:
                self.router_table[destination] = [port, total_distance, api.current_time()]
        # add default host route
        self.host_route_default(destination, api.current_time()) 

    def handle_timer(self):
        """
        Called periodically.

        When called, your router should send tables to neighbors.  It
        also might not be a bad place to check for whether any entries
        have expired.

        """
        # remove expired routes
        remove_dests = []
    
        for dest, info in self.router_table.items():
            time = api.current_time() - info[2]
            if time >= self.ROUTE_TIMEOUT:
                remove_dests.append(dest);
        for dest in remove_dests:
            # remove routes
            del self.router_table[dest]
            if self.POISON_MODE:
                self.poison.append(dest)
            self.host_route_default(dest, api.current_time())

        # send to neighbors the router_table
        for port in self.port_latency.keys():
            for dest, info in self.router_table.items():
                if (info[0] != port):
                    self.send(basics.RoutePacket(dest, info[1]), port)
                elif (info[0] == port and self.POISON_MODE):
                    self.send(basics.RoutePacket(dest, INFINITY), port)
            if self.POISON_MODE:
                for dest in self.poison:
                    if dest not in self.host_port:
                        self.send(basics.RoutePacket(dest, INFINITY), port)
        self.poison = []