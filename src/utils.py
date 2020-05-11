def split_into_chunks(message: bytes, max_length):
    """Splits a message into chunks. Prefers to split at newlines."""
    if len(message) < max_length:
        return [message]

    split_index = max_length
    newline_index = 0
    last_newline_index = -1
    while newline_index >= 0:
        last_newline_index = newline_index
        newline_index = message.find(b'\n', newline_index + 1, split_index)

    if last_newline_index > 0:
        # Split and discard the newline.
        split_index = last_newline_index
        second = message[split_index + 1:]
    else:
        # Split and keep the non-newline character.
        second = message[split_index:]

    first = message[:split_index]

    return [first] + split_into_chunks(second, max_length)

def discord_postprocess(message: str) -> str:
    """Postprocesses a message for the Discord platform. This entails
       replacing double newlines with single newlines this also entails
       turning discord account names into mentions"""
    message = message.replace('\n\n', '\n')
    lines = message.split('\n')
    line_index = 0
    for line in lines:
        words = line.split()
        index = 0
        for word in words:
            if word.startswith('discord/'):  # the name command will still run because the result is enclosed in back ticks so this would be read as `discord/ and not discord/
                words[index] = f'<@{word.strip("discord/")}>'
            index += 1
        line = ''
        for word in words:
            line += word + ' '
        lines[line_index] = line
        line_index += 1


    message = ''
    for line in lines:
        message += line + '\n'
    return message
