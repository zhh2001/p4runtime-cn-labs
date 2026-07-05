#include <core.p4>
#include <v1model.p4>

const bit<16> ETHERTYPE_IPV4 = 0x0800;
typedef bit<9> port_t;

header ethernet_t {
    bit<48> dst_addr;
    bit<48> src_addr;
    bit<16> ether_type;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> total_len;
    bit<16> identification;
    bit<3>  flags;
    bit<13> frag_offset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> checksum;
    bit<32> src_addr;
    bit<32> dst_addr;
}

struct headers_t {
    ethernet_t ethernet;
    ipv4_t ipv4;
}

struct metadata_t { }

parser PacketParser(
    packet_in packet,
    out headers_t hdr,
    inout metadata_t meta,
    inout standard_metadata_t standard_meta)
{
    state start {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type) {
            ETHERTYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
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
    action drop() {
        mark_to_drop(standard_meta);
    }

    action rewrite_and_forward(
        bit<48> src_mac,
        bit<48> dst_mac,
        port_t port)
    {
        hdr.ethernet.src_addr = src_mac;
        hdr.ethernet.dst_addr = dst_mac;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
        standard_meta.egress_spec = port;
    }

    table route_v4 {
        key = {
            hdr.ipv4.dst_addr: lpm;
        }
        actions = {
            rewrite_and_forward;
            drop;
        }
        size = 1024;
        default_action = drop();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            route_v4.apply();
        } else {
            drop();
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
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            {
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.diffserv,
                hdr.ipv4.total_len,
                hdr.ipv4.identification,
                hdr.ipv4.flags,
                hdr.ipv4.frag_offset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                hdr.ipv4.src_addr,
                hdr.ipv4.dst_addr
            },
            hdr.ipv4.checksum,
            HashAlgorithm.csum16);
    }
}

control PacketDeparser(packet_out packet, in headers_t hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}

@pkginfo(
    name = "p4runtime-cn-labs/02-table-entry",
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
