#include <core.p4>
#include <v1model.p4>

const bit<9> CPU_PORT = 510;

@controller_header("packet_in")
header packet_in_t {
    @id(1) bit<16> ingress_port;
    @id(2) bit<8> reason;
}

@controller_header("packet_out")
header packet_out_t {
    @id(1) bit<16> egress_port;
}

header ethernet_t {
    bit<48> dst_addr;
    bit<48> src_addr;
    bit<16> ether_type;
}

struct headers_t {
    packet_in_t packet_in;
    packet_out_t packet_out;
    ethernet_t ethernet;
}

struct metadata_t { }

parser PacketParser(
    packet_in packet,
    out headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_meta)
{
    state start {
        transition select(standard_meta.ingress_port) {
            CPU_PORT: parse_packet_out;
            default: parse_ethernet;
        }
    }

    state parse_packet_out {
        packet.extract(hdr.packet_out);
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

control VerifyPacketChecksum(
    inout headers_t hdr,
    inout metadata_t meta)
{
    apply { }
}

control IngressPipe(
    inout headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_meta)
{
    action punt(bit<8> reason) {
        hdr.packet_in.setValid();
        hdr.packet_in.ingress_port = (bit<16>) standard_meta.ingress_port;
        hdr.packet_in.reason = reason;
        standard_meta.egress_spec = CPU_PORT;
    }

    action drop() {
        mark_to_drop(standard_meta);
    }

    table punt_policy {
        key = {
            hdr.ethernet.dst_addr: exact;
        }
        actions = {
            punt;
            drop;
        }
        const default_action = punt(1);
        size = 32;
    }

    apply {
        if (hdr.packet_out.isValid()) {
            standard_meta.egress_spec = (bit<9>) hdr.packet_out.egress_port;
            hdr.packet_out.setInvalid();
        } else {
            punt_policy.apply();
        }
    }
}

control EgressPipe(
    inout headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_meta)
{
    apply { }
}

control ComputePacketChecksum(
    inout headers_t hdr,
    inout metadata_t meta)
{
    apply { }
}

control PacketDeparser(packet_out packet, in headers_t hdr) {
    apply {
        packet.emit(hdr.packet_in);
        packet.emit(hdr.ethernet);
    }
}

@pkginfo(
    name = "p4runtime-cn-labs/07-stream-arbitration",
    version = "0.1.0"
)
V1Switch(
    PacketParser(),
    VerifyPacketChecksum(),
    IngressPipe(),
    EgressPipe(),
    ComputePacketChecksum(),
    PacketDeparser()
) main;
