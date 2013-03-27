"""
<title>FloodPlusIngress</title>
<description>
    Flood to all ports plus send to ingress port

    Generate a packet
    Generate and install a matching flow
    Add action to flood the packet
    Add action to send to ingress port
    Send the packet to ingress dataplane port
    Verify the packet is received at all other ports
    
</description>
"""

try:
    if('TWISTER_ENV' in globals()):
        from ce_libs.openflow.of_13.openflow_base import *
        testbed=currentTB
        from ce_libs import ra_proxy
        ra_service=ra_proxy                        
except:
    raise

class FloodPlusIngress(SimpleDataPlane):
    """
    Flood to all ports plus send to ingress port

    Generate a packet
    Generate and install a matching flow
    Add action to flood the packet
    Add action to send to ingress port
    Send the packet to ingress dataplane port
    Verify the packet is received at all other ports
    """
    def runTest(self):
        self.logger.info("Running FloodPlusIngress test")
        of_ports = self.port_map.keys()
        of_ports.sort()
        self.assertTrue(len(of_ports) > 0, "Not enough ports for test")

        pkt = testutils.simple_tcp_packet()
        act = action.action_output()
        for ingress_port in of_ports:
            self.logger.info("Clear the switch state")
            rv = testutils.delete_all_flows(self.controller, self.logger)
            self.assertEqual(rv, 0, "Failed to delete all flows")

            self.logger.info("Ingress " + str(ingress_port) + " to all ports")

            portmatch = match.in_port(ingress_port)
            srcmatch = match.eth_src(parse.parse_mac("00:06:07:08:09:0a"))
            dstmatch = match.eth_dst(parse.parse_mac("00:01:02:03:04:05"))
            request = message.flow_mod()
            request.match_fields.tlvs.append(portmatch)
            request.match_fields.tlvs.append(srcmatch)
            request.match_fields.tlvs.append(dstmatch)
            request.buffer_id = 0xffffffff
            act.port = ofp.OFPP_FLOOD
            inst = instruction.instruction_apply_actions()
            inst.actions.add(act)
            act.port = ofp.OFPP_IN_PORT
            inst.actions.add(act)
            request.instructions.add(inst)
            logMsg('logDebug',"Request send to switch:")
            logMsg('logDebug',request.show())
            self.logger.info("Inserting flow")
            rv = self.controller.message_send(request)
            self.assertTrue(rv != -1, "Error installing flow mod")

            self.logger.info("Sending packet to dp port " + str(ingress_port))
            self.dataplane.send(ingress_port, str(pkt))
            testutils.receive_pkt_check(self.dataplane, pkt, of_ports, [], self, self.logger)

    
tc = FloodPlusIngress()
_RESULT = tc.run()
