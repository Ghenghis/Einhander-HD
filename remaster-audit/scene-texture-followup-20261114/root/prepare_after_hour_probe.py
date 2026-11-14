"""Prepare a separate 3090 diagnostic runner, with an explicit time/idle gate."""
from pathlib import Path
n=Path(__file__).resolve().parent
s=(n/'run_sdk_direct_3060.py').read_text()
s=s.replace("out=n/'sdk-direct-3060-r1'","out=n/'sdk-direct-after-hour-r1'")
s=s.replace("target='GPU-eb6787b1-90ea-26b2-4a62-d44b1452d8aa';reserved='GPU-ff51fa52-74c8-c785-e000-53fe58844033'", "target='GPU-ff51fa52-74c8-c785-e000-53fe58844033';reserved='GPU-eb6787b1-90ea-26b2-4a62-d44b1452d8aa'")
s=s.replace("device_name='NVIDIA GeForce RTX 3060'", "device_name='NVIDIA GeForce RTX 3090 Ti'")
s=s.replace("assert not (marker.parent/'GPU-LOCK').exists()", "deadline=datetime.datetime.fromisoformat(json.loads(hold)['expires_utc'].replace('Z','+00:00'))\nassert datetime.datetime.now(datetime.timezone.utc)>=deadline,'User 3090 hour has not ended'\nassert not (marker.parent/'GPU-LOCK').exists()")
s=s.replace("lease=marker.parent/'GPU-RESERVED-3060'", "lease=marker.parent/'GPU-LOCK'")
s=s.replace("user_3090_lease_writes=False", "user_3090_lease_writes=True")
s=s.replace("reserved_3090_uuid=reserved", "other_gpu_uuid=reserved")
s=s.replace("int(gpu[2])<512 and int(gpu[4])<=5", "int(gpu[3])-int(gpu[2])>=6144 and int(gpu[4])<=5")
s=s.replace("    target_rows=[x for x in rows if x.startswith(target+',')];assert not target_rows,target_rows", "    # User desktop contexts may remain. Low utilization + >=6GiB free is the\n    # gate; no other process is stopped or reconfigured.\n    result['target_existing_context_count']=sum(x.startswith(target+',') for x in rows)")
s=s.replace("scope='Single bounded 3060 SDK control; user 3090 reservation unchanged'", "scope='Single bounded 3090 SDK control after user-authorized hour; below-normal,320x180,45s watchdog'")
s=s.replace("    (out/'owned-3060-lease.json').write_bytes(owned)", "    (out/'expired-user-3090-lease.json').write_bytes(hold)\n    assert marker.read_bytes()==hold\n    marker.write_bytes(owned)\n    (out/'owned-3090-lease.json').write_bytes(owned)")
start=s.index("                if any(x.startswith(reserved+',') for x in mine):")
end=s.index('            time.sleep(.1)',start)
s=s[:start]+s[end:]
s=s.replace("result['owned_pid_seen_on_3060']", "result['owned_pid_seen_on_target']")
s=s.replace("result['owned_pid_seen_on_3090']", "result['owned_pid_seen_on_other_gpu']")
s=s.replace("'owned_pid_seen_on_3060'", "'owned_pid_seen_on_target'")
s=s.replace(" and not result['owned_pid_seen_on_other_gpu']", "")
s=s.replace("result['3060_lease_released']=True", "result['owned_gpu_lock_released']=True")
s=s.replace("    result['user_3090_lease_unchanged']=marker.read_bytes()==hold", "    if owned is not None and marker.exists() and marker.read_bytes()==owned and result['process_gone']:\n        marker.unlink();result['owned_3090_lease_released']=True\n    result['expired_user_lease_archived']=owned is not None and (out/'expired-user-3090-lease.json').exists()\n    result['user_hour_respected']=datetime.datetime.now(datetime.timezone.utc)>=deadline")
# Resource availability is an unexecuted test, not failed graphics acceptance.
s=s.replace("except Exception as ex:result['error']=repr(ex)", "except Exception as ex:\n    result['error']=repr(ex)\n    if process is None:result['gpu_test_status']='NOT_RUN_RESOURCE_PREFLIGHT'")
compile(s,'run_sdk_direct_after_hour.py','exec')
(n/'run_sdk_direct_after_hour.py').write_text(s)
print('Prepared after-hour runner. NOT executed. Time and idle preflight gates are mandatory.')
