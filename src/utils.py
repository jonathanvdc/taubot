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
