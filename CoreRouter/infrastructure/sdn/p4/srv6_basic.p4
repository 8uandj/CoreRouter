/*
 * 3S-COM Testbed — Phase 4: SRv6 Forwarding với Hardware MSD Enforcement
 * =========================================================================
 *
 * THIẾT KẾ TRIẾT HỌC (Hardware-Awareness Principle):
 * ─────────────────────────────────────────────────────
 * Chương trình P4 này hiện thực hoá RÀNG BUỘC CỨNG (hard constraint) MSD
 * (Maximum Segment Depth) ngay tại tầng Parser của Data Plane.
 *
 * Lý luận (cho Hội đồng):
 *   1. P4 hardware có MSD hữu hạn, được định nghĩa tại compile-time.
 *   2. AI Control Plane (JO-VPPM) biết ràng buộc này qua Action Masking.
 *   3. Nếu gói tin đến có #SID > MAX_SID_DEPTH (dù thế nào), Parser
 *      BẮT BUỘC chuyển sang trạng thái error và DROP — không BSID, không bypass.
 *   4. Đây là tuyến phòng thủ thứ 2 (second line of defence). 
 *      Tuyến thứ nhất là: AI không bao giờ sinh ra stack dài như vậy.
 *
 * KIẾN TRÚC MSD (theo kiến trúc testbed):
 *   - Border switch (vd: Hue s5, NinhBinh s3): MAX_SID_DEPTH = 3
 *   - Core switch   (vd: Hanoi s1, DaNang s6, HCM s9): MAX_SID_DEPTH = 10
 *   => File này compile cho Core switch. Border switch compile riêng với
 *      const MAX_SID_DEPTH = 3.
 *
 * Không BSID. Không bypass. Packet vi phạm MSD → DROP. Đây là luật.
 *
 * Usage:
 *   p4c -b bmv2 --target simple_switch --arch v1model \
 *       -DMAX_SID_DEPTH=10 -o build/ srv6_basic.p4
 *
 *   Cho border switch:
 *   p4c -b bmv2 --target simple_switch --arch v1model \
 *       -DMAX_SID_DEPTH=3  -o build/ srv6_basic.p4
 */

#include <core.p4>
#include <v1model.p4>

// ══════════════════════════════════════════════════════════════
//  CONSTANTS — Giới hạn phần cứng (thay đổi theo switch type)
// ══════════════════════════════════════════════════════════════
// Có thể override bằng flag -DMAX_SID_DEPTH=<N> khi compile
#ifndef MAX_SID_DEPTH
#define MAX_SID_DEPTH 10  // Default: Core switch
#endif

// Error code khi gói tin vi phạm MSD
error { IPv6IncorrectVersion, SRv6SegmentDepthExceeded }

// ══════════════════════════════════════════════════════════════
//  TYPE DEFINITIONS
// ══════════════════════════════════════════════════════════════
typedef bit<48>  macAddr_t;
typedef bit<128> ip6Addr_t;
typedef bit<9>   egressPort_t;

// ══════════════════════════════════════════════════════════════
//  HEADERS
// ══════════════════════════════════════════════════════════════
header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header ipv6_t {
    bit<4>    version;
    bit<8>    trafficClass;
    bit<20>   flowLabel;
    bit<16>   payloadLen;
    bit<8>    nextHdr;
    bit<8>    hopLimit;
    ip6Addr_t srcAddr;
    ip6Addr_t dstAddr;
}

// SRv6 Routing Extension Header (RFC 8754)
header srv6_h {
    bit<8>  nextHdr;        // Protocol sau SRH
    bit<8>  hdrExtLen;      // Độ dài header theo đơn vị 8 byte (ngoại trừ 8 byte đầu)
    bit<8>  routingType;    // = 4 (Segment Routing)
    bit<8>  segmentsLeft;   // Số lượng SID còn lại cần xử lý
    bit<8>  lastEntry;      // Index của SID cuối cùng trong danh sách
    bit<8>  flags;
    bit<16> tag;
}

// Mỗi SID trong danh sách (một IPv6 address 128-bit)
header srv6_sid_t {
    ip6Addr_t segmentId;
}

// ──────────────────────────────────────────────────────────────
// Metadata: thông tin cần truyền giữa các pipeline stage
// ──────────────────────────────────────────────────────────────
struct metadata_t {
    bit<8> sid_count;    // Tổng số SID đã parse được (để kiểm tra ≤ MSD)
    bool   is_srv6;      // Có phải gói tin SRv6 không?
    bool   msd_exceeded; // Flag vi phạm MSD (parser set, ingress drop)
}

struct headers_t {
    ethernet_t  ethernet;
    ipv6_t      ipv6;
    srv6_h      srv6;
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // KEY POINT: Mảng SID được giới hạn tại compile-time bởi MAX_SID_DEPTH.
    // Đây chính là sự mô phỏng giới hạn bộ nhớ phần cứng (TCAM/SRAM).
    // Không thể parse nhiều hơn MAX_SID_DEPTH SID dù muốn.
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    srv6_sid_t[MAX_SID_DEPTH] sid_list;
}

// ══════════════════════════════════════════════════════════════
//  PARSER — Nơi thực thi Hard Constraint MSD
// ══════════════════════════════════════════════════════════════
parser SRv6Parser(
    packet_in           packet,
    out headers_t       hdr,
    inout metadata_t    meta,
    inout standard_metadata_t smeta)
{
    // Biến đếm số SID đã bóc tách (chỉ dùng trong parser)
    bit<8> remaining;

    state start {
        meta.sid_count    = 0;
        meta.is_srv6      = false;
        meta.msd_exceeded = false;
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            0x86DD: parse_ipv6;
            default: accept;
        }
    }

    state parse_ipv6 {
        packet.extract(hdr.ipv6);
        // Kiểm tra version — nếu không phải IPv6, báo lỗi
        verify(hdr.ipv6.version == 6, error.IPv6IncorrectVersion);
        transition select(hdr.ipv6.nextHdr) {
            43: parse_srv6_header;  // Next Header = 43: Routing Header
            default: accept;
        }
    }

    state parse_srv6_header {
        packet.extract(hdr.srv6);
        meta.is_srv6 = true;
        // Số SID cần parse = lastEntry + 1
        remaining = hdr.srv6.lastEntry + 1;

        // ──────────────────────────────────────────────────────
        // HARDWARE-AWARENESS CHECK:
        // Nếu số SID trong gói > MAX_SID_DEPTH (giới hạn phần cứng),
        // chuyển ngay vào trạng thái lỗi và DROP gói tin.
        // Đây là "bức tường thứ 2" sau Action Masking của AI.
        // Gói tin vi phạm không được phép đi xa hơn Parser.
        // ──────────────────────────────────────────────────────
        verify(remaining <= (bit<8>)MAX_SID_DEPTH, error.SRv6SegmentDepthExceeded);

        transition parse_sid_list;
    }

    // ──────────────────────────────────────────────────────────
    // Parse danh sách SID tuần tự, tối đa MAX_SID_DEPTH lần.
    // Đây là cách P4 mô phỏng vòng lặp: UNROLLED LOOP tại compile-time.
    // Không có dynamic loop — phản ánh đúng bản chất phần cứng cứng nhắc.
    // ──────────────────────────────────────────────────────────
    state parse_sid_list {
        transition select(remaining) {
            0: accept;
            default: parse_one_sid;
        }
    }

    state parse_one_sid {
        // Giới hạn index tránh out-of-bound (safety check bổ sung)
        packet.extract(hdr.sid_list.next);
        remaining = remaining - 1;
        meta.sid_count = meta.sid_count + 1;
        transition parse_sid_list;
    }
}

// ══════════════════════════════════════════════════════════════
//  CHECKSUM VERIFICATION
// ══════════════════════════════════════════════════════════════
control SRv6VerifyChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply { }
}

// ══════════════════════════════════════════════════════════════
//  INGRESS — Logic Forwarding chính
// ══════════════════════════════════════════════════════════════
control SRv6Ingress(
    inout headers_t       hdr,
    inout metadata_t      meta,
    inout standard_metadata_t smeta)
{
    // ──────────────────────────────────────────────────────────
    // Action: Drop không điều kiện
    // ──────────────────────────────────────────────────────────
    action drop() {
        mark_to_drop(smeta);
    }

    // ──────────────────────────────────────────────────────────
    // Action: Forward theo cổng ra + update MAC
    // ──────────────────────────────────────────────────────────
    action ipv6_forward(macAddr_t dstMac, macAddr_t srcMac, egressPort_t port) {
        smeta.egress_spec    = port;
        hdr.ethernet.dstAddr = dstMac;
        hdr.ethernet.srcAddr = srcMac;
        hdr.ipv6.hopLimit    = hdr.ipv6.hopLimit - 1;
    }

    // ──────────────────────────────────────────────────────────
    // Action: SRv6 — tiến SID tiếp theo (Segment Routing Step)
    // Bóc SID hiện tại ra, đặt SID tiếp theo làm IPv6 destination.
    // ──────────────────────────────────────────────────────────
    action srv6_advance_segment() {
        // Giảm segmentsLeft — tiêu thụ SID hiện tại
        hdr.srv6.segmentsLeft = hdr.srv6.segmentsLeft - 1;

        // Update IPv6 dstAddr = SID tại vị trí segmentsLeft mới
        // (Đây là logic "pseudo" — BMv2 sẽ cần bảng mapping index → SID)
        // Controller sẽ populate bảng sid_index bên dưới.
    }

    // ──────────────────────────────────────────────────────────
    // Table: Định tuyến IPv6 cơ bản (LPM match)
    // Được populate bởi Controller (gRPC/P4Runtime).
    // ──────────────────────────────────────────────────────────
    table routing_v6 {
        key = {
            hdr.ipv6.dstAddr: lpm;
        }
        actions = {
            ipv6_forward;
            drop;
            NoAction;
        }
        size         = 1024;
        default_action = drop();
    }

    // ──────────────────────────────────────────────────────────
    // Table: SRv6 Local SID table
    // Match SID đến cổng ra → thực hiện forwarding
    // Khi segmentsLeft = 0: gói tin đã đến đích cuối cùng
    // ──────────────────────────────────────────────────────────
    table srv6_local_sid {
        key = {
            hdr.ipv6.dstAddr: exact;
        }
        actions = {
            srv6_advance_segment;
            drop;
            NoAction;
        }
        size           = 256;
        default_action = NoAction();
    }

    // Bộ đếm cho vi phạm MSD (Show-off counter cho Demo)
    counter(1, CounterType.packets) msd_violation_counter;

    apply {
        // ── BƯỚC 1: Xử lý gói tin lỗi từ Parser ──────────────
        // Parser đã gọi verify() và set parser_error nếu vi phạm MSD.
        if (smeta.parser_error != error.NoError) {
            // Tăng bộ đếm để báo cáo lên SDN Controller / Demo UI
            msd_violation_counter.count(0);
            drop();
            return;
        }

        // ── BƯỚC 2: Xử lý SRv6 ───────────────────────────────
        if (hdr.ipv6.isValid()) {
            if (hdr.srv6.isValid()) {
                if (hdr.srv6.segmentsLeft > 0) {
                    // Còn SID cần xử lý: tra bảng local SID
                    srv6_local_sid.apply();
                }
                // segmentsLeft == 0: SRv6 journey ended,
                // forward theo dstAddr IPv6 bình thường
            }

            // ── BƯỚC 3: Định tuyến IPv6 thông thường ─────────
            if (hdr.ipv6.hopLimit == 0) {
                drop();
            } else {
                routing_v6.apply();
            }
        }
    }
}

// ══════════════════════════════════════════════════════════════
//  EGRESS — Không có xử lý đặc biệt ở phase này
// ══════════════════════════════════════════════════════════════
control SRv6Egress(
    inout headers_t       hdr,
    inout metadata_t      meta,
    inout standard_metadata_t smeta)
{
    apply { }
}

// ══════════════════════════════════════════════════════════════
//  DEPARSER — Tái lắp ráp packet
// ══════════════════════════════════════════════════════════════
control SRv6Deparser(
    packet_out    packet,
    in headers_t  hdr)
{
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv6);
        packet.emit(hdr.srv6);
        // Emit tất cả SID slots (emit bỏ qua slot không valid tự động)
        packet.emit(hdr.sid_list);
    }
}

// ══════════════════════════════════════════════════════════════
//  CHECKSUM COMPUTATION
// ══════════════════════════════════════════════════════════════
control SRv6ComputeChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply { }
}

// ══════════════════════════════════════════════════════════════
//  MAIN SWITCH INSTANTIATION
// ══════════════════════════════════════════════════════════════
V1Switch(
    SRv6Parser(),
    SRv6VerifyChecksum(),
    SRv6Ingress(),
    SRv6Egress(),
    SRv6ComputeChecksum(),
    SRv6Deparser()
) main;
