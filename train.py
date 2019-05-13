import math
import time
import torch
import argparse
import os
import logging
from torch import optim, nn
from torch.utils.data import DataLoader
from net import CityscapesNet
from evaluate import evaluate
from dataset import CityscapesDataset


def train(net, device, trainloader, testloader, lr, max_epochs, early_stop, checkpoint_filename):
    logger = logging.getLogger('training')
    logger.setLevel(logging.INFO)
    log_format = logging.Formatter('%(asctime)s - %(message)s')
    fh = logging.FileHandler(checkpoint_filename + '.log')
    fh.setFormatter(log_format)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(log_format)
    logger.addHandler(ch)

    def log_status(*args):
        logger.info('epoch {}, train loss {}, test loss {}, test accuracy {:.2f}'.format(*args))

    net.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(net.parameters(), lr=lr)

    n_train_batches = len(trainloader)
    n_classes = len(CityscapesDataset.classes)

    # (epoch, train_loss, test_loss, accuracy)
    best = (0, math.inf, math.inf, 0.0)

    stop_in = early_stop

    logger.info('started training')

    for epoch in range(max_epochs):
        net.train()
        train_loss = 0.0
        for (images, labels) in trainloader:
            images = images.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            outputs = net(images)
            outputs = outputs.permute(0, 2, 3, 1).contiguous().view(-1, n_classes)
            labels = labels.view(-1)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        train_loss /= n_train_batches

        accuracy, test_loss = evaluate(net, device, testloader, criterion)

        status = (epoch, train_loss, test_loss, accuracy)
        if test_loss < best[2]:
            stop_in = early_stop
            best = status
            torch.save(net.state_dict(), checkpoint_filename)
        else:
            stop_in -= 1

        log_status(*status)

        if stop_in == 0:
            break

    logger.info('finished training, best result:')
    log_status(*best)

    net.load_state_dict(torch.load(checkpoint_filename))


def main():
    parser = argparse.ArgumentParser(description='Train cityscapes model',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--traindata', default=os.path.join('data', 'cityscapes', 'Training'),
                        help='directory containing training dataset')
    parser.add_argument('--testdata', default=os.path.join('data', 'cityscapes', 'Test'),
                        help='directory containing validation dataset')
    parser.add_argument('--checkpoint', default='cityscapes.pt', help='checkpoint filename')
    parser.add_argument('--device', default='cpu', help='device to use')
    parser.add_argument('--batch', default=8, help='batch size')
    parser.add_argument('--lr', default=0.001, help='learning rate')
    parser.add_argument('--epochs', default=100, help='max number of epochs')
    parser.add_argument('--earlystop', default=5, help='early stop after this many epochs without improvement')
    args = parser.parse_args()

    net = CityscapesNet(3, len(CityscapesDataset.classes))

    trainset = CityscapesDataset(args.traindata, random_flips=True)
    trainloader = DataLoader(trainset, batch_size=args.batch, shuffle=True, num_workers=4)

    testset = CityscapesDataset(args.testdata, random_flips=False)
    testloader = DataLoader(testset, batch_size=args.batch, shuffle=True, num_workers=4)

    train(net, args.device, trainloader, testloader, args.lr, args.epochs, args.earlystop, args.checkpoint)


if __name__ == '__main__':
    main()