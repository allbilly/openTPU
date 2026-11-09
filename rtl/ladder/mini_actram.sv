// Ladder step 6 — ACT RAM: int8 activation bytes + the per-(row, block) scale record.
//
// The production layout (docs/isa.md "Quantization", opentpu/isasim.py Slice.act/ascale/adoff):
//   act    [ACT_ROWS][ACT_BLOCKS*D]  int8   the quantized activation bytes of each row
//   ascale [ACT_ROWS][ACT_BLOCKS]    fp32   the row's scale Sa of each K-block
//   adoff  [ACT_ROWS][ACT_BLOCKS][4] uint8  the four sub-block offsets da of each K-block
// The quantizer writes it (one byte / one record word per cycle; DUP uses the second write
// port), the step-7 MXU reads it through the combinational read ports.  Arrays are flat and
// remain visible so tb_mini can dump them for the bit-exact comparison with isasim.
`timescale 1ns/1ps
module mini_actram #(
  parameter int D          = 32,
  parameter int ACT_BLOCKS = 16,
  parameter int ACT_ROWS   = 4
) (
  input  logic        clk,

  // quantizer write port 0: one ACT byte
  input  logic        we,
  input  logic [31:0] wrow,      // row index
  input  logic [31:0] wlin,      // byte index inside the row: block*D + i
  input  logic [7:0]  wdata,
  // quantizer duplicate write port (QACT DUP: row + rows in the same cycle)
  input  logic        we2,
  input  logic [31:0] wrow2,
  input  logic [31:0] wlin2,
  input  logic [7:0]  wdata2,
  // quantizer scale-record write port: Sa (fp32 bits) and the packed four da bytes
  input  logic        swe,
  input  logic [31:0] srow,
  input  logic [31:0] sblock,
  input  logic [31:0] sdata,     // Sa bits
  input  logic        dwe,
  input  logic [31:0] drow,
  input  logic [31:0] dblock,
  input  logic [31:0] ddata,     // {da3, da2, da1, da0}

  // MXU read ports (step 7): combinational
  input  logic [31:0] rrow,
  input  logic [31:0] rlin,
  output logic [7:0]  rdata,
  input  logic [31:0] rrow_s,
  input  logic [31:0] rblock_s,
  output logic [31:0] rdata_s,
  input  logic [31:0] rrow_d,
  input  logic [31:0] rblock_d,
  output logic [31:0] rdata_d,
  // step-7 MXU wide ports: four consecutive int8 bytes (word address inside the row, byte 0
  // in bits [7:0]) and the whole scale record {da3,da2,da1,da0, Sa} in one 64-bit word
  input  logic [31:0] rrow_w,
  input  logic [31:0] rword,
  output logic [31:0] rdata_w,
  input  logic [31:0] rrow_rec,
  input  logic [31:0] rblock_rec,
  output logic [63:0] rdata_rec
);

  localparam int ROW_BYTES = ACT_BLOCKS * D;

  logic [7:0]  act   [0:ACT_ROWS*ROW_BYTES-1];
  logic [31:0] ascale [0:ACT_ROWS*ACT_BLOCKS-1];
  logic [31:0] adoff  [0:ACT_ROWS*ACT_BLOCKS-1];
  integer i;

  initial begin
    for (i = 0; i < ACT_ROWS * ROW_BYTES; i = i + 1) begin
      act[i] = 8'd0;
    end
    for (i = 0; i < ACT_ROWS * ACT_BLOCKS; i = i + 1) begin
      ascale[i] = 32'd0;
      adoff[i]  = 32'd0;
    end
  end

  assign rdata   = act[rrow * ROW_BYTES + rlin];
  assign rdata_s = ascale[rrow_s * ACT_BLOCKS + rblock_s];
  assign rdata_d = adoff[rrow_d * ACT_BLOCKS + rblock_d];
  assign rdata_w = act[rrow_w * ROW_BYTES + rword * 4 + 32'd3] << 24
                 | act[rrow_w * ROW_BYTES + rword * 4 + 32'd2] << 16
                 | act[rrow_w * ROW_BYTES + rword * 4 + 32'd1] << 8
                 | act[rrow_w * ROW_BYTES + rword * 4];
  assign rdata_rec = {adoff[rrow_rec * ACT_BLOCKS + rblock_rec],
                      ascale[rrow_rec * ACT_BLOCKS + rblock_rec]};

  always_ff @(posedge clk) begin
    if (we) begin
      act[wrow * ROW_BYTES + wlin] <= wdata;
    end
    if (we2) begin
      act[wrow2 * ROW_BYTES + wlin2] <= wdata2;
    end
    if (swe) begin
      ascale[srow * ACT_BLOCKS + sblock] <= sdata;
    end
    if (dwe) begin
      adoff[drow * ACT_BLOCKS + dblock] <= ddata;
    end
  end

endmodule
