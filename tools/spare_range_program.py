"""Full-address coverage schedule and decoder for chunked raw BIST.

Preparation only: the caller must separately establish image/calibration,
exclusive hardware ownership and the selected power/traffic conditions.
"""
CAPACITY = 1 << 31
DEFAULT_CHUNK = 4 << 20


def schedule(chunk_bytes=DEFAULT_CHUNK):
    assert chunk_bytes > 0 and chunk_bytes % 64 == 0 and CAPACITY % chunk_bytes == 0
    assert chunk_bytes <= DEFAULT_CHUNK
    operations=[]
    for generation in (0,1):
        # Keep both channels' complete contents resident before verifying.
        for write in (True,False):
            for ch in (0,1):
                seed=(0x96a53cc35aa56969 if ch==0 else 0x694ac33ca55a9696)
                if generation:seed^=(1<<64)-1
                bases=list(range(0,CAPACITY,chunk_bytes))
                if not write:bases.reverse()
                for base in bases:
                    operations.append(dict(generation=generation,channel=ch,write=write,
                                           base=base,length=chunk_bytes//64,seed=seed))
    return operations


def expected_word(word_address,seed,modules):
    assert modules in (8,9) and 0<=word_address<(1<<25) and 0<=seed<(1<<64)
    address_mask=(1<<25)-1;group_mask=(1<<(modules*8))-1
    concatenated=word_address|((word_address^address_mask)<<25)|(word_address<<50)
    group=(concatenated^(seed|(seed<<64)))&group_mask
    return b''.join(group.to_bytes(modules,'little') for _ in range(8))


def validate_result(operation,result,capture,previous_epoch):
    """First raw payload is distinct from counters covering the whole chunk."""
    op=operation;modules=8 if op['channel']==0 else 9
    assert op['base']%64==0 and op['length']>0 and op['base']+64*op['length']<=CAPACITY
    assert result['beats']==op['length'] and 0<result['ticks']<2**32
    assert capture['sequence']==(previous_epoch+1)&0xffffffff
    if op['write']:
        assert capture['valid']==0 and capture['returns']==0
        return dict(first_bad_bytes=[],errors=0)
    assert capture['valid']==1 and capture['returns']==op['length']
    assert capture['base']==op['base']//64 and capture['mode']==3 and capture['seed']==op['seed']
    actual=bytes.fromhex(capture['actual']);want=expected_word(op['base']//64,op['seed'],modules)
    assert len(actual)==len(want)==modules*8
    xor=bytes(a^b for a,b in zip(actual,want));first_mask=0
    for i in range(8):first_mask|=int.from_bytes(xor[i*modules:(i+1)*modules],'little')
    errors=result['errors'];mask=result['dq_mask'];lanes=result['lane_errors']
    assert len(lanes)==modules and 0<=mask<(1<<(8*modules))
    assert 0<=errors<=op['length'] and all(0<=count<=errors for count in lanes)
    assert errors<=sum(lanes) and bool(errors)==bool(mask)
    assert all(bool(mask>>(8*i)&255)==bool(count) for i,count in enumerate(lanes))
    assert first_mask & ~mask == 0
    if first_mask:assert errors>0
    return dict(first_bad_bytes=[i for i,value in enumerate(xor) if value],errors=errors)
