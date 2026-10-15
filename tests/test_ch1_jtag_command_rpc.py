"""Exercise the actual Tcl command/ack loop before using it for model weights."""
import subprocess
from tools.fedora_run_ch1_jtag_lfm2_fast import COMMAND_PROC

MAGIC=0x4f54504a


def exercise(frame,replies):
    # First scan submits the command. Every later scan polls; all replies
    # are supplied explicitly so missing/stale completions cannot be hidden.
    mock='''set scans {}
set idles {}
proc scan_dr_hw_jtag {bits option value} {
 global scans replies
 lappend scans $value
 if {[llength $scans]==1} {return 0}
 if {![llength $replies]} {error "unexpected extra poll"}
 set result [lindex $replies 0]
 set replies [lrange $replies 1 end]
 return $result
}
proc runtest_hw_jtag {args} {global idles; lappend idles $args}
'''
    script=mock+'\n'+COMMAND_PROC+f'\nset replies {{{" ".join(format(x,"x") for x in replies)}}}\n'
    script+=f'if {{[catch {{otpu_command {frame:x}}} result]}} {{puts "ERR $result"}} else {{puts "OK $result"}}\n'
    script+='puts "SCANS [llength $scans]"\nputs "IDLES [llength $idles]"\n'
    result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True,check=True)
    assert not result.stderr,result.stderr
    return result.stdout.splitlines()


def request(seq=7,op=4):
    return 0x1234|0x80000040<<512|15<<544|op<<548|seq<<556|MAGIC<<572


def reply(seq=7,status=0,data=0):
    return data|status<<512|seq<<520|MAGIC<<536


def test_full_512_bit_data_and_completion_are_retained():
    data=(1<<511)|0x0123456789abcdef
    lines=exercise(request(op=3),[reply(data=data)])
    assert int(lines[0].split()[1],16)==data
    assert lines[1:]==['SCANS 2','IDLES 1']


def test_stale_completion_is_polled_without_sending_another_request():
    lines=exercise(request(),[reply(seq=6),reply(data=0xabcd)])
    assert int(lines[0].split()[1],16)==0xabcd
    assert lines[1:]==['SCANS 3','IDLES 1']


def test_hardware_command_error_stops_after_its_response():
    lines=exercise(request(),[reply(status=2)])
    assert lines[0]=='ERR Mailbox command failed with status 2'
    assert lines[1:]==['SCANS 2','IDLES 1']


def test_invalid_header_cannot_reach_the_cable():
    lines=exercise(request(seq=0),[])
    assert lines[0]=='ERR Bad command header'
    assert lines[1:]==['SCANS 0','IDLES 0']


def test_bad_response_magic_stops_before_another_request():
    lines=exercise(request(),[7<<520])
    assert lines[0]=='ERR Mailbox response magic mismatch'
    assert lines[1:]==['SCANS 2','IDLES 1']
