""" Sustained Attention to Response Task (SART)

Author: Cary Stothart (cary.stothart@gmail.com)
Date: 05/11/2015
Version: 2.0
Tested on StandalonePsychoPy-1.82.01-win32

################################# DESCRIPTION #################################

This module contains the standard SART task as detailed by Robertson et al. 
(1997). 

The following task attributes can be easily modified (see the sart()
function documentation below for details):
    
1) Number of blocks (default is 1)
2) Number of font size by number repetitions per trial (default is 5)
3) Target number (default is 3)
4) The presentation order of the numbers. Specifically, the
   numbers can be presented randomly or in a fixed fashion. (default is random)
5) Whether or not practice trials should be presented at the beginning of the 
   task.
   
How to use:

1. Install PsychoPy if you haven't already.
2. Load this file and run it using PsychoPy. Participants will be run on the 
   classic SART task (Robertson et al, 1997) unless one of the sart()
   function parameters is changed.

Reference:

Robertson, H., Manly, T., Andrade, J.,  Baddeley, B. T., & Yiend, J. (1997). 
'Oops!': Performance correlates of everyday attentional failures in traumatic 
brain injured and normal subjects. Neuropsychologia, 35(6), 747-758.

################################## FUNCTIONS ##################################

Self-Contained Functions (Argument=Default Value):

sart(monitor="testMonitor", blocks=1, reps=5, omitNum=3, practice=True, 
     path="", fixed=False)
     
monitor......The monitor to be used for the task.
blocks.......The number of blocks to be presented.
reps.........The number of repetitions to be presented per block.  Each
             repetition equals 45 trials (5 font sizes X 9 numbers).
omitNum......The number participants should withhold pressing a key on.
practice.....If the task should display 18 practice trials that contain 
             feedback on accuracy.
path.........The directory in which the output file will be placed. Defaults
             to the directory in which the task is placed.
fixed........Whether or not the numbers should be presented in a fixed
             instead of random order (e.g., 1, 2, 3, 4, 5, 6, 7, 8 ,9,
             1, 2, 3, 4, 5, 6, 7, 8, 9...).     
             
################################### CITATION ##################################

How to cite this software in APA:

Stothart, C. (2015). Python SART (Version 2) [software]. Retrieved from 
https://github.com/cstothart/python-cog-tasks.  

For a DOI and other citation information, please see 
http://figshare.com/authors/Cary_Stothart/394277
     
################################## COPYRIGHT ##################################

The MIT License (MIT)

Copyright (c) 2015 Cary Robert Stothart

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.     

"""

import argparse
import os
import random
import sys
import time
from pathlib import Path

from sart_data import (
    CONDITIONS, GENDERS, INFO_FIELDS, SCHOOL_YEARS, TOPICS, ExperimentStore,
    extract_info_values, validate_participant_info, validate_settings,
)

SART_PRE_REPS = 5       # 225 main trials, about 4 min 19 sec plus display overhead
SART_POST_REPS = 12     # 540 main trials, about 10 min 21 sec plus display overhead
OMIT_NUMBER = 3
PRACTICE = False
FIXED_ORDER = False
RESULT_PATH = Path(__file__).resolve().parent / "experiment"
SHOW_COUNTDOWN = True
SHOW_RESPONSE_FEEDBACK = True
EXIT_KEY = "escape"

# Import lazily so CSV validation and automated tests do not need a display.
visual = core = data = event = gui = None


def load_psychopy():
    global visual, core, data, event, gui
    if visual is None:
        from psychopy import visual, core, data, event, gui


class ExperimentAbort(Exception):
    """ESC or a cancelled participant dialog."""


def check_exit(keys):
    if EXIT_KEY in keys:
        raise ExperimentAbort()


def sart(monitor="testMonitor", blocks=1, reps=5, omitNum=3, practice=False,
         path=None, fixed=False, phase="pre", fullscr=True, part_info=None):
    """Run PRE/POST SART and accumulate linked CSV tables in experiment/.

    Completed trials are flushed after each trial, including practice trials.
    Summary metrics exclude practice. An interrupted current trial is discarded.
    """
    validate_settings(blocks, reps, omitNum, phase)
    load_psychopy()
    output_path = RESULT_PATH if path in (None, "") else Path(path)
    while True:
        try:
            info = part_info_gui() if part_info is None else validate_participant_info(part_info)
            store = ExperimentStore(output_path, info, phase, blocks=blocks, reps=reps,
                                    omit_number=omitNum, fixed=fixed, practice=practice,
                                    response_feedback=SHOW_RESPONSE_FEEDBACK)
            break
        except ExperimentAbort:
            print("Participant dialog cancelled. No run was created.")
            return None
        except ValueError as exc:
            if part_info is not None:
                raise
            error = gui.Dlg(title="Check participant/session information")
            error.addText(str(exc))
            error.show()
            if not error.OK:
                return None

    win = None
    status = "ERROR"
    summary = None
    try:
        win = visual.Window(fullscr=fullscr, size=(1000, 700), color="black",
                            units="cm", monitor=monitor)
        sart_init_inst(win, omitNum)
        if practice:
            sart_prac_inst(win, omitNum)
            if SHOW_COUNTDOWN:
                sart_countdown(win)
            sart_block(win, fb=True, omitNum=omitNum, reps=1, bNum=0,
                       fixed=fixed, on_trial=store.record_trial)
        sart_act_task_inst(win)
        if SHOW_COUNTDOWN:
            sart_countdown(win)
        for block in range(1, blocks + 1):
            sart_block(win, fb=SHOW_RESPONSE_FEEDBACK, omitNum=omitNum,
                       reps=reps, bNum=block, fixed=fixed, on_trial=store.record_trial)
            if blocks > 1 and block != blocks:
                sart_break_inst(win)
        status = "COMPLETED"
    except ExperimentAbort:
        status = "ABORTED"
    finally:
        try:
            summary = store.finish(status)
            print_summary(summary, status)
            print(f"CSV directory: {store.path}")
            print(f"Run ID: {store.run_id}")
            if win is not None and status != "ERROR":
                show_final_feedback(win, summary, status)
        finally:
            store.close()
            if win is not None:
                win.close()
    return summary


def _fmt_pct(value):
    return "NA" if value is None else f"{value:.1f}%"


def _fmt_ms(value):
    return "NA" if value is None else f"{value:.1f} ms"


def _fmt_cv(value):
    return "NA" if value is None else f"{value:.3f}"


def print_summary(summary, status="COMPLETED"):
    print(f"\nSART RESULT - {status}")
    print(f"Completed main trials: {summary['completed_trials']}")
    print(f"Overall accuracy: {_fmt_pct(summary['overall_accuracy_pct'])}")
    print(f"Balanced accuracy: {_fmt_pct(summary['balanced_accuracy_pct'])}")
    print(f"Go omissions: {summary['go_omissions']} / {summary['go_trials']} "
          f"({_fmt_pct(summary['go_omission_rate_pct'])})")
    print(f"No-Go commissions: {summary['nogo_commission_errors']} / {summary['nogo_trials']} "
          f"({_fmt_pct(summary['nogo_commission_rate_pct'])})")
    print(f"Median correct Go RT: {_fmt_ms(summary['median_correct_go_rt_ms'])}")
    print(f"Mean correct Go RT: {_fmt_ms(summary['mean_correct_go_rt_ms'])}")
    print(f"Go RT SD: {_fmt_ms(summary['go_rt_sd_ms'])}; CV: {_fmt_cv(summary['go_rt_cv'])}")
    for window in summary['time_bins']:
        metrics = window['metrics']
        suffix = ' (partial)' if window['is_partial'] else ''
        print(f"{window['start_s'] / 60:g}-{window['end_s'] / 60:g} min{suffix}: "
              f"N={metrics['completed_trials']}, "
              f"Go omission={_fmt_pct(metrics['go_omission_rate_pct'])}, "
              f"No-Go commission={_fmt_pct(metrics['nogo_commission_rate_pct'])}, "
              f"Median RT={_fmt_ms(metrics['median_correct_go_rt_ms'])}")
    first = summary['first_4min']
    suffix = ' (partial)' if summary['first_4min_partial'] else ''
    print(f"First 4 min{suffix}: N={first['completed_trials']}, "
          f"Median RT={_fmt_ms(first['median_correct_go_rt_ms'])}\n")


def show_final_feedback(win, summary, status="COMPLETED"):
    message = (
        f"{'Experiment stopped with ESC.' if status == 'ABORTED' else 'Block complete.'}\n\n"
        f"Go omission rate: {_fmt_pct(summary['go_omission_rate_pct'])}\n"
        f"No-Go commission rate: {_fmt_pct(summary['nogo_commission_rate_pct'])}\n"
        f"Balanced accuracy: {_fmt_pct(summary['balanced_accuracy_pct'])}\n"
        f"Median Go RT: {_fmt_ms(summary['median_correct_go_rt_ms'])}\n"
        f"Go RT CV: {_fmt_cv(summary['go_rt_cv'])}\n\nPress SPACE to finish."
    )
    stim = visual.TextStim(win, text=message, color="white", height=0.6, pos=(0, 0))
    event.clearEvents()
    while True:
        stim.draw()
        win.flip()
        keys = event.getKeys(keyList=["space", EXIT_KEY])
        if "space" in keys or EXIT_KEY in keys:
            break


def part_info_gui():
    values = ["", "1", TOPICS[0], CONDITIONS[0], "Please Select", "",
              "Please Select", "Please Select", ""]
    choices = [None, ["1", "2", "3"], list(TOPICS), list(CONDITIONS),
               ["Please Select", *GENDERS], None, ["Please Select", *SCHOOL_YEARS],
               ["Please Select", "Yes", "No"], None]
    while True:
        info = gui.Dlg(title="SART")
        info.addText("Participant and Session Info")
        for label, value, options in zip(INFO_FIELDS, values, choices):
            if options:
                # Both old wx and new Qt PsychoPy accept an index for dropdown initial.
                info.addField(label, initial=options.index(value), choices=options)
            else:
                info.addField(label, initial=value)
        info.show()
        if not info.OK:
            raise ExperimentAbort()
        values = extract_info_values(info.data)
        try:
            return validate_participant_info(values)
        except ValueError as exc:
            error = gui.Dlg(title="Check participant information")
            error.addText(str(exc))
            error.show()
            if not error.OK:
                raise ExperimentAbort()


def sart_init_inst(win, omitNum):
    inst = visual.TextStim(win, text=("In this task, a series of numbers will" +
                                      " be presented to you.  For every" +
                                      " number that appears except for the" +
                                      " number " + str(omitNum) + ", you are" +
                                      " to press the space bar as quickly as" +
                                      " you can.  That is, if you see any" +
                                      " number but the number " +
                                      str(omitNum) + ", press the space" +
                                      " bar.  If you see the number " +
                                      str(omitNum) + ", do not press the" +
                                      " space bar or any other key.\n\n" +
                                      "Please give equal importance to both" +
                                      " accuracy and speed while doing this" + 
                                      " task.\n\nPress the b key when you" +
                                      " are ready to start."), 
                           color="white", height=0.7, pos=(0, 0))
    event.clearEvents()
    while True:
        keys = event.getKeys(keyList=['b', EXIT_KEY])
        check_exit(keys)
        if 'b' in keys:
            break
        inst.draw()
        win.flip()
        
def sart_prac_inst(win, omitNum):
    inst = visual.TextStim(win, text=("We will now do some practice trials " +
                                      "to familiarize you with the task.\n" +
                                      "\nRemember, press the space bar when" +
                                      " you see any number except for the " +
                                      " number " + str(omitNum) + ".\n\n" +
                                      "Press the b key to start the " +
                                      "practice."), 
                           color="white", height=0.7, pos=(0, 0))
    event.clearEvents()
    while True:
        keys = event.getKeys(keyList=['b', EXIT_KEY])
        check_exit(keys)
        if 'b' in keys:
            break
        inst.draw()
        win.flip()
        
def sart_act_task_inst(win):
    inst = visual.TextStim(win, text=("We will now start the actual task.\n" +
                                      "\nRemember, give equal importance to" +
                                      " both accuracy and speed while doing" +
                                      " this task.\n\nPress the b key to " +
                                      "start the actual task."), 
                           color="white", height=0.7, pos=(0, 0))
    event.clearEvents()
    while True:
        keys = event.getKeys(keyList=['b', EXIT_KEY])
        check_exit(keys)
        if 'b' in keys:
            break
        inst.draw()
        win.flip()
        
def sart_countdown(win):
    """PsyToolkit-like get-ready countdown."""
    for value in ["3", "2", "1"]:
        stim = visual.TextStim(
            win, text=value, color="white",
            height=2.0, pos=(0, 0)
        )
        stim.draw()
        win.flip()

        start = time.perf_counter()
        while time.perf_counter() - start < 0.7:
            keys = event.getKeys(keyList=[EXIT_KEY])
            check_exit(keys)
            core.wait(0.01)

    win.flip()
    core.wait(0.2)


def sart_break_inst(win):
        inst = visual.TextStim(win, text=("You will now have a 60 second " +
                                          "break.  Please remain in your " +
                                          "seat during the break."),
                               color="white", height=0.7, pos=(0, 0))
        nbInst = visual.TextStim(win, text=("You will now do a new block of" +
                                            " trials.\n\nPress the b key " +
                                            "bar to begin."),
                                 color="white", height=0.7, pos=(0, 0))
        startTime = time.perf_counter()
        while 1:
            check_exit(event.getKeys(keyList=[EXIT_KEY]))
            eTime = time.perf_counter() - startTime
            inst.draw()
            win.flip()
            if eTime > 60:
                break
        event.clearEvents()
        while True:
            keys = event.getKeys(keyList=['b', EXIT_KEY])
            check_exit(keys)
            if 'b' in keys:
                break
            nbInst.draw()
            win.flip()


def sart_block(win, fb, omitNum, reps, bNum, fixed, on_trial=None):
    mouse = event.Mouse(visible=False, win=win)
    xStim = visual.TextStim(win, text="X", height=3.35, color="white", pos=(0, 0))
    circleStim = visual.Circle(win, radius=1.50, lineWidth=8,
                               lineColor="white", pos=(0, -0.2))
    numStim = visual.TextStim(win, font="Arial", color="white", pos=(0, 0))
    # Build feedback once; creating a TextStim during a response can delay frames.
    errorStim = visual.TextStim(win, text="X", color="white", height=1.2, pos=(0, 0))
    sizes = [1.20, 3.00] if bNum == 0 else [1.20, 1.80, 2.35, 2.50, 3.00]
    factorial = data.createFactorialTrialList({"number": list(range(1, 10)), "fontSize": sizes})
    if fixed:
        remaining = factorial.copy()
        sequence = []
        for _ in sizes:
            for number in range(1, 10):
                choices = [trial for trial in remaining if trial["number"] == number]
                chosen = random.choice(choices)
                sequence.append(chosen)
                remaining.remove(chosen)
    else:
        sequence = factorial
    trials = data.TrialHandler(sequence, nReps=reps,
                              method="sequential" if fixed else "random")
    clock = core.Clock()
    completed = []
    block_start = time.perf_counter()
    try:
        for trial_num, trial in enumerate(trials, start=1):
            row = sart_trial(win, fb, omitNum, xStim, circleStim, numStim,
                             errorStim, clock, trial['fontSize'], trial['number'],
                             trial_num, bNum, mouse)
            # Record here, before returning the block, so ESC cannot lose prior trials.
            if on_trial is not None:
                on_trial(row)
            completed.append(row)
    finally:
        if completed:
            average_ms = (time.perf_counter() - block_start) / len(completed) * 1000.0
            print(f"Block {bNum}: {len(completed)} completed trials; "
                  f"mean wall time/trial {average_ms:.1f} ms")
    return completed


def sart_trial(win, fb, omitNum, xStim, circleStim, numStim, errorStim,
               clock, fontSize, number, tNum, bNum, mouse):
    """250 ms digit + 900 ms mask; SPACE responds, ESC aborts current trial.

    Reset the response clock on the stimulus flip, rather than before drawing.
    No-Go commission feedback is a white X inside the existing mask interval.
    """
    mouse.setVisible(False)
    numStim.setHeight(fontSize)
    numStim.setText(str(number))
    responded = False
    response_rt = None
    feedback_until = None
    response_deadline = None
    onset = {}

    def mark_onset():
        clock.reset()
        onset["perf_s"] = time.perf_counter()

    event.clearEvents()
    numStim.draw()
    win.callOnFlip(mark_onset)
    win.flip()
    digit_start = onset["perf_s"]

    def read_response():
        nonlocal responded, response_rt, feedback_until
        for key, rt in event.getKeys(keyList=["space", EXIT_KEY], timeStamped=clock):
            if key == EXIT_KEY:
                raise ExperimentAbort()
            if (key == "space" and not responded and rt >= 0
                    and (response_deadline is None or rt <= response_deadline)):
                responded = True
                response_rt = float(rt)
                if fb and number == omitNum:
                    feedback_until = time.perf_counter() + 0.2

    while time.perf_counter() - digit_start < 0.25:
        read_response()
        core.wait(0.002)

    # Draw the first mask immediately, then measure its duration from the flip.
    def draw_mask():
        if fb and feedback_until is not None and time.perf_counter() < feedback_until:
            errorStim.draw()
        else:
            xStim.draw()
            circleStim.draw()

    draw_mask()
    win.flip()
    mask_start = time.perf_counter()
    response_deadline = mask_start + 0.90 - digit_start
    while time.perf_counter() - mask_start < 0.90:
        read_response()
        draw_mask()
        win.flip()
    # Drain responses through the end of the response window before clearing it.
    read_response()
    win.flip()
    end_time = time.perf_counter()
    accuracy = int(responded if number != omitNum else not responded)
    return {
        "is_practice": bNum == 0, "block_num": int(bNum), "trial_num": int(tNum),
        "stimulus": int(number), "omit_number": int(omitNum),
        "trial_type": "nogo" if number == omitNum else "go",
        "responded": responded, "accuracy": accuracy,
        "rt_ms": response_rt * 1000.0 if response_rt is not None else None,
        "font_size_cm": float(fontSize), "stimulus_onset_perf_s": digit_start,
        "trial_end_perf_s": end_time,
    }


def main(argv=None):
    # PsychoPy 2026 reads Korean locale JSON with the process default encoding.
    # Re-exec this entry point in UTF-8 mode on Windows, without changing packages.
    if sys.platform == "win32" and not sys.flags.utf8_mode:
        os.execv(sys.executable, [sys.executable, "-X", "utf8", *sys.argv])
    parser = argparse.ArgumentParser(description="Run a PRE or POST SART task.")
    parser.add_argument("--phase", choices=("pre", "post"))
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    parser.add_argument("--windowed", action="store_true")
    args = parser.parse_args(argv)
    phase = args.phase
    if phase is None:
        try:
            phase = input("phase 입력 (pre/post): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 0
    if phase not in ("pre", "post"):
        print("pre 또는 post를 입력하세요.")
        return 1
    sart(blocks=1, reps=SART_PRE_REPS if phase == "pre" else SART_POST_REPS,
         omitNum=OMIT_NUMBER, practice=PRACTICE, path=args.output,
         fixed=FIXED_ORDER, phase=phase, fullscr=not args.windowed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

