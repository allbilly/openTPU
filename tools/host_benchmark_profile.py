"""Optional elapsed-time observations on one benchmark's existing objects.

No payloads, register values or device counters are changed. Nested durations
are reported separately; concurrent-thread totals are never a wall-time split.
"""
from functools import wraps
import threading
import time


class HostProfiler:
    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.lock = threading.RLock()
        self.thread = threading.local()
        self.phase = 'STARTING'
        self.phase_started = clock()
        self.phase_intervals = []
        self.operations = {}
        self.attachments = []
        self.active_calls = 0
        self.closed = False

    def set_phase(self, phase):
        if not isinstance(phase, str) or not phase:
            raise ValueError('A nonempty benchmark phase is required')
        with self.lock:
            if self.closed:
                raise RuntimeError('Host profile is closed')
            if phase != self.phase:
                now = self.clock()
                self.phase_intervals.append(dict(phase=self.phase,
                    elapsed_seconds=now-self.phase_started, complete=True))
                self.phase, self.phase_started = phase, now

    def attach(self, obj, names, prefix):
        """Wrap only this instance, retaining and restoring existing overrides."""
        with self.lock:
            if self.closed:
                raise RuntimeError('Host profile is closed')
            targets = []
            for name in names:
                original = getattr(obj, name)
                if not callable(original):
                    raise TypeError('Profile target is not callable: '+name)
                if any(target is obj and member == name for target, member, *_ in self.attachments):
                    raise ValueError('Profile target is already attached: '+name)
                if any(row[1] == name for row in targets):
                    raise ValueError('Duplicate profile target: '+name)
                had_override = name in vars(obj)
                previous = vars(obj).get(name)
                wrapped = self._wrapped(original, prefix+'.'+name)
                targets.append((obj, name, had_override, previous, wrapped))
            installed = []
            try:
                for row in targets:
                    setattr(obj, row[1], row[4])
                    installed.append(row)
            except BaseException:
                for _, name, had_override, previous, _ in reversed(installed):
                    if had_override:
                        setattr(obj, name, previous)
                    else:
                        delattr(obj, name)
                raise
            self.attachments.extend(installed)

    def _wrapped(self, original, label):
        @wraps(original)
        def observed(*args, **kwargs):
            stack = getattr(self.thread, 'stack', None)
            if stack is None:
                stack = self.thread.stack = []
            with self.lock:
                closed = self.closed
                phase = self.phase
                if not closed:
                    self.active_calls += 1
            if closed:
                return original(*args, **kwargs)
            frame = dict(start=self.clock(), child_seconds=0.)
            stack.append(frame)
            failed = False
            try:
                return original(*args, **kwargs)
            except BaseException:
                failed = True
                raise
            finally:
                elapsed = self.clock()-frame['start']
                stack.pop()
                if stack:
                    stack[-1]['child_seconds'] += elapsed
                with self.lock:
                    self.active_calls -= 1
                    row = self.operations.setdefault((phase, label),
                        dict(calls=0, failed_calls=0, inclusive_seconds=0.,
                             self_seconds=0., max_seconds=0.))
                    row['calls'] += 1
                    row['failed_calls'] += int(failed)
                    row['inclusive_seconds'] += elapsed
                    row['self_seconds'] += max(0., elapsed-frame['child_seconds'])
                    row['max_seconds'] = max(row['max_seconds'], elapsed)
        observed.__profile_label__ = label
        return observed

    def snapshot(self):
        with self.lock:
            intervals = [dict(row) for row in self.phase_intervals]
            if not self.closed:
                intervals.append(dict(phase=self.phase,
                    elapsed_seconds=self.clock()-self.phase_started, complete=False))
            return dict(enabled=True, closed=self.closed, active_calls=self.active_calls,
                units='elapsed seconds, not CPU time', phase_assignment='phase at call entry',
                interpretation='Inclusive times contain nested calls. Self times exclude same-thread profiled children. Threads can overlap; neither sum is a partition of benchmark wall time. Instrumentation adds overhead.',
                phase_intervals=intervals,
                operations=[dict(phase=phase, operation=label, **row)
                            for (phase, label), row in sorted(self.operations.items())],
                attached_methods=sorted({wrapped.__profile_label__
                    for _, _, _, _, wrapped in self.attachments}))

    def close(self):
        with self.lock:
            if self.closed:
                return
            if self.active_calls:
                raise RuntimeError('Finish profiled worker calls before restoring methods')
            for obj, name, _, _, wrapped in self.attachments:
                if vars(obj).get(name) is not wrapped:
                    raise RuntimeError('Profile target changed ownership: '+name)
            for obj, name, had_override, previous, _ in reversed(self.attachments):
                if had_override:
                    setattr(obj, name, previous)
                else:
                    delattr(obj, name)
            self.phase_intervals.append(dict(phase=self.phase,
                elapsed_seconds=self.clock()-self.phase_started, complete=True))
            self.closed = True
