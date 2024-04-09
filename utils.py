import json

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from sklearn import preprocessing

DATA_DIRECTORY_NAME = "data"
CHAR_TO_RAD_FILENAME = "kanji_to_radical.json"
CHAR_TO_RAD_DIRECTORY = f"{DATA_DIRECTORY_NAME}/{CHAR_TO_RAD_FILENAME}"
ENG_TO_CHARS_FILENAME = "english_to_kanji.json"
ENG_TO_CHARS_DIRECTORY = f"{DATA_DIRECTORY_NAME}/{ENG_TO_CHARS_FILENAME}"


def get_tensor_from_word(word: str, eng_tens: torch.Tensor, eng_vocab: list[str]):
    word_to_idx_dict = {vocab: idx for idx, vocab in enumerate(eng_vocab)}
    if word not in word_to_idx_dict:
        raise RuntimeError("Word is not in vocabulary!")
    idx = word_to_idx_dict[word]
    for tens in eng_tens:
        if tens[idx] == 1.:
            return tens
    raise RuntimeError("Corresponding tensor for word was not found!")


def json_to_dict(json_file: str) -> dict:
    """
    Load json file and return it as a dict
    :param json_file:
    :return:
    """
    with open(json_file, encoding='utf-8') as f:
        data = json.load(f)
    f.close()
    return dict(data)


def dict_to_tensors(eng_to_rad: dict):
    """
    Converts the dict of English words to radicals into tensors that can be used by the network
    :return:
    """
    # encodes and creates tensors of the input and output
    encoder_eng = preprocessing.LabelBinarizer()
    encoder_rad = preprocessing.MultiLabelBinarizer()
    encoded_eng = encoder_eng.fit_transform(list(eng_to_rad.keys()))
    encoded_rad = encoder_rad.fit_transform(eng_to_rad.values())
    eng_tensor = torch.tensor(encoded_eng, dtype=torch.float32)
    rad_tensor = torch.tensor(encoded_rad, dtype=torch.float32)
    assert eng_tensor.size(0) == rad_tensor.size(0)
    return eng_tensor, rad_tensor, encoder_eng.classes_, encoder_rad.classes_


def create_eng_to_rads(kanji_to_rads, eng_to_kanji) -> dict[str, list[str]]:
    """
    Use the kanji to radical dictionary and English to
    Character dictionary to construct the English to radical dictionary
    :param kanji_to_rads:
    :param eng_to_kanji:
    :return: dict of English words to radicals
    """

    eng_to_rads = dict()
    for eng_word in eng_to_kanji:
        # Create new dict entry for English word
        eng_to_rads[eng_word] = []
        for kanji in eng_to_kanji[eng_word]:
            # Add unique radicals to English word entry
            if kanji in kanji_to_rads:
                for rad in kanji_to_rads[kanji]:
                    if rad not in eng_to_rads[eng_word]:
                        eng_to_rads[eng_word].append(rad)
    return eng_to_rads


def load_eng_to_rads() -> dict[str, list[str]]:
    """
    Loads English words to radicals based on a Kanji to radical mapping, and English to Kanji mapping
    :return:
    """
    kanji_to_rads = json_to_dict(CHAR_TO_RAD_DIRECTORY)
    eng_to_kanji = json_to_dict(ENG_TO_CHARS_DIRECTORY)
    eng_to_rads = create_eng_to_rads(kanji_to_rads, eng_to_kanji)
    return eng_to_rads


def train_model(model: nn.Module,
                eng_tensors: torch.Tensor,
                rad_tensors: torch.Tensor,
                optimizer: optim.Optimizer,
                criterion=nn.MSELoss(),
                epochs=100,
                scheduler: optim.lr_scheduler.LRScheduler = None,
                verbose=False):
    """
    Trains the model based on all of its information and parameters
    :param model:
    :param eng_tensors:
    :param rad_tensors:
    :param optimizer:
    :param criterion:
    :param epochs:
    :param scheduler:
    :param verbose: Whether to print the loss during training
    :return:
    """
    loss = 0
    for epoch in range(0, epochs):
        for eng, rad in zip(eng_tensors, rad_tensors):
            # Zero the gradient buffers
            optimizer.zero_grad()
            # Self as the model
            output = model(eng)
            loss = criterion(output, rad)
            loss.backward()
            # Update
            optimizer.step()
        if scheduler is not None:
            scheduler.step()
        if epoch % 1000 == 0 or epoch < 100:
            print_verbose(
                "Epoch {: >8} Loss: {}".format(epoch + 1, loss.data.numpy()),
                verbose=verbose
            )


class KanjiFFNN(nn.Module):
    def __init__(self, eng_vocab_size: int, radical_vocab_size: int, nodes: int):
        super(KanjiFFNN, self).__init__()
        # Hidden layer
        self.hid1 = nn.Linear(eng_vocab_size, nodes)
        self.hid2 = nn.Linear(nodes, radical_vocab_size)

    def forward(self, x):
        """
        Forward propagation of the model
        :param x: Data
        :return:
        """
        # print("Forward start!")
        # Pass input x to hidden layer
        # print(x)
        x = self.hid1(x)
        # Apply ReLU activation function to output of first layer
        # print(x)
        x = F.relu(x)
        # Apply second hidden layer
        # print(x)
        x = self.hid2(x)
        # Pass the output from the previous layer to the output layer
        # print(x)
        x = F.sigmoid(x)
        # print(x)
        # print("Forward end!")
        return x

    def train_fit(self,
                  eng_tensors: torch.Tensor,
                  rad_tensors: torch.Tensor,
                  optimizer: optim.Optimizer,
                  criterion=nn.MSELoss(),
                  epochs=100,
                  scheduler: optim.lr_scheduler.LRScheduler = None,
                  verbose=False):
        """
        Forwards itself to train_model function
        :param eng_tensors:
        :param rad_tensors:
        :param optimizer:
        :param criterion:
        :param epochs:
        :param scheduler:
        :param verbose:
        :return:
        """
        return train_model(self, eng_tensors, rad_tensors, optimizer, criterion, epochs, scheduler, verbose)


def print_verbose(*values, verbose):
    """
    Prints verbose information based on data provided
    :param values:
    :param verbose:
    :return:
    """
    if verbose:
        print(*values)
