"""
<title>MatchETHsrc</title>
<description>
    Verify flow_mod matches on ethernet src
    
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

class MatchETHsrc(SimpleDataPlane):
    """
    Verify flow_mod matches on ethernet src
    """
    def runTest(self):
        self.logger.info("Running MatchETHsrc test")
        self.logger.info("Insert flowmod and verify it matches on eth SRC")
        of_ports = self.port_map.keys()
        of_ports.sort()
        self.assertTrue(len(of_ports) > 0, "Not enough ports for test")

        pkt = testutils.simple_tcp_packet()
        act = action.action_output()
        ingress_port = of_ports[0]
        egress_port = of_ports[1]
        self.logger.info("Clear the switch state, delete all flows")
        rv = testutils.delete_all_flows(self.controller, self.logger)
        self.assertEqual(rv, 0, "Failed to delete all flows")
        self.logger.info("Insert flow_mod")
        srcmatch = match.eth_src(parse.parse_mac("00:06:07:08:09:0a"))
        request = message.flow_mod()
        request.match_fields.tlvs.append(srcmatch)
        request.buffer_id = 0xffffffff
        act.port = of_ports[1]
        inst = instruction.instruction_apply_actions()
        inst.actions.add(act)
        request.instructions.add(inst)
        self.logger.info("Inserting flow")
        logMsg('logDebug',"Request send to switch:")
        logMsg('logDebug',request.show())
        rv = self.controller.message_send(request)
        self.assertTrue(rv != -1, "Error installing flow mod")

        self.logger.info("Sending packet to dp port " + str(ingress_port))
        self.dataplane.send(ingress_port, str(pkt))
        testutils.receive_pkt_check(self.dataplane, pkt, [egress_port], [ingress_port],self,self.logger)
        testutils.do_barrier(self.controller)

        #Send a non matching packet, verify it is droped
        pkt2 = testutils.simple_tcp_packet(dl_src="00:11:22:33:11:12")
        self.dataplane.send(ingress_port, str(pkt2))
        testutils.receive_pkt_check(self.dataplane, pkt, [], of_ports,self,self.logger)

    
tc = MatchETHsrc()
_RESULT = tc.run()