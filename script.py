import re
from pathlib import Path

import gradio as gr
import subprocess
import random as rnd

from modules import chat, shared
from modules.utils import gradio
params = {
    'display_name': 'Balabolka TTS',
    'activate': True,
    'selected_service': 'Microsoft',
    'selected_language': 'en-US',
    'selected_voice': 'Monica',
    'autoplay': True,
}
# Config example
#   -s Microsoft 
#   -l es-MX 
#   -n Dalia
def load_config():
    global params
    cfg_path = Path('extensions/balabolka_tts/balabolka/bal4web.cfg').resolve()
    if not cfg_path.exists():
        save_config()
        return
    with open('extensions/balabolka_tts/balabolka/bal4web.cfg', 'r') as f:
        for line in f.readlines():
            if line.startswith('#'):
                continue
            if line.startswith('-s'):
                params['selected_service'] = line.split(' ')[1].strip()
            if line.startswith('-l'):
                params['selected_language'] = line.split(' ')[1].strip()
            if line.startswith('-n'):
                params['selected_voice'] = line.split(' ')[1].strip()

def save_config():
    global params
    cfg_path = Path('extensions/balabolka_tts/balabolka/bal4web.cfg').resolve()
    with open(cfg_path, 'w') as f:
        f.write(f'-s {params["selected_service"]}\n')
        f.write(f'-l {params["selected_language"]}\n')
        f.write(f'-n {params["selected_voice"]}\n')

def remove_surrounded_chars(string):
    # this expression matches to 'as few symbols as possible (0 upwards) between any asterisks' OR
    # 'as few symbols as possible (0 upwards) between an asterisk and the end of the string'
    return re.sub('\*[^\*]*?(\*|$)', '', string)


def state_modifier(state):
    if not params['activate']:
        return state

    state['stream'] = False
    return state


def input_modifier(string):
    if not params['activate']:
        return string

    shared.processing_message = "*Is recording a voice message...*"
    return string


def history_modifier(history):
    # Remove autoplay from the last reply
    if len(history['internal']) > 0:
        history['visible'][-1] = [
            history['visible'][-1][0],
            history['visible'][-1][1].replace('controls autoplay>', 'controls>')
        ]

    return history

def gen_audio_balabolka(string : str, path_to_audio : Path):
    global params
    
    print(f'Generating audio for {string}')
    path_to_balabolka = Path('extensions/balabolka_tts/balabolka/bal4web.exe').resolve()

    print(f'Path to balabolka: {path_to_balabolka}')
    if not path_to_balabolka.exists():
        return "Balabolka not found"
    
    print(f'Path to audio: {path_to_audio}')
    path_to_text_file = path_to_audio.parent / 'text.txt'

    print(f'Path to text file: {path_to_text_file}')
    with open(path_to_text_file.as_posix(), 'w') as f:
        f.write(string)
    
    print(f'Generating audio with parameters: -f {path_to_text_file.resolve().as_posix()} -w {path_to_audio.resolve().as_posix()}')
    exec_parameters = f'-f {path_to_text_file.resolve().as_posix()} -w {path_to_audio.resolve().as_posix()}'

    print(f'Full command: {path_to_balabolka.as_posix()} {exec_parameters}')
    subprocess.call(f'{path_to_balabolka.as_posix()} {exec_parameters}', creationflags=subprocess.CREATE_NO_WINDOW)
    

def output_modifier(string):
    global params

    if not params['activate']:
        return string

    original_string = string
    string = remove_surrounded_chars(string)
    string = string.replace('"', '')
    string = string.replace('“', '')
    string = string.replace('\n', ' ')
    string = string.strip()
    if string == '':
        string = 'Empty reply, try regenerating'

    random_name = str(hash(string)) + rnd.randint(0, 1000000).__str__()

    output_file = Path(f'extensions/balabolka_tts/outputs/{random_name}.wav').resolve()
    print(f'Outputting audio to {str(output_file)}')
    try:
        gen_audio_balabolka(string, output_file)
        autoplay = 'autoplay' if params['autoplay'] else ''
        string = f'<audio src="file/{output_file.as_posix()}" controls {autoplay}></audio>'
    except Exception as e:
        string = f'Error: {e}\n\n'
    except:
        string = f'Error: Unknown error\n\n'

    if params['show_text']:
        string += f'\n\n{original_string}'

    shared.processing_message = "*Is typing...*"
    return string

def change_and_save(value, params_key):
    global params
    params.update({params_key: value})
    save_config()

def ui():
    load_config()
    # Gradio elements
    with gr.Row():
        activate = gr.Checkbox(value=params['activate'], label='Activate TTS')
        autoplay = gr.Checkbox(value=params['autoplay'], label='Play TTS automatically')

    with gr.Row():
        service = gr.Textbox(value=params['selected_service'], label='TTS Service')
        language = gr.Textbox(value=params['selected_language'], label='Language')
        voice = gr.Textbox(value=params['selected_voice'], label='Voice')

    with gr.Row():
        convert = gr.Button('Permanently replace audios with the message texts')
        convert_cancel = gr.Button('Cancel', visible=False)
        convert_confirm = gr.Button('Confirm (cannot be undone)', variant="stop", visible=False)

    if shared.is_chat():
        # Convert history with confirmation
        convert_arr = [convert_confirm, convert, convert_cancel]
        convert.click(lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)], None, convert_arr)
        convert_confirm.click(
            lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr).then(
            remove_tts_from_history, gradio('history'), gradio('history')).then(
            chat.save_persistent_history, gradio('history', 'character_menu', 'mode'), None).then(
            chat.redraw_html, shared.reload_inputs, gradio('display'))

        convert_cancel.click(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr)


    # Event functions to update the parameters in the backend
    activate.change(lambda x: params.update({'activate': x}), activate, None)
    
    voice.change(lambda x: change_and_save(x, 'selected_voice'), voice, None)
    language.change(lambda x: change_and_save(x, 'selected_language'), language, None)
    service.change(lambda x: change_and_save(x, 'selected_service'), service, None)

    # Event functions to update the parameters in the backend
    autoplay.change(lambda x: params.update({"autoplay": x}), autoplay, None)
