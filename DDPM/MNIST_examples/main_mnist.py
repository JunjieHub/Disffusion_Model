'''
this file reproduce the training process from
https://github.com/alirezadir/Machine-Learning-Interviews/blob/main/src/MLSD/ml-system-design.md
'''

import torch
import torchvision
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader
from diffusers import DDPMScheduler, UNet2DModel
from matplotlib import pyplot as plt
import os
import glob

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f'Using device: {device}')

def corrupt(x, amount):
  """Corrupt the input `x` by mixing it with noise according to `amount`"""
  noise = torch.rand_like(x)
  amount = amount.view(-1, 1, 1, 1) # Sort shape so broadcasting works
  return x*(1-amount) + noise*amount

def monitoring(losses, net, save_folder='monitor', epoch=None):
    # Plot losses and some samples
    fig, axs = plt.subplots(1, 2, figsize=(12, 5))

    # Losses
    axs[0].plot(losses)
    axs[0].set_ylim(0, 0.1)
    axs[0].set_title('Loss over time')

    # Samples
    n_steps = 40
    x = torch.rand(64, 1, 28, 28).to(device)
    for i in range(n_steps):
        noise_amount = torch.ones((x.shape[0], )).to(device) * (1-(i/n_steps)) # Starting high going low
        with torch.no_grad():
            pred = net(x, 0).sample
        mix_factor = 1/(n_steps - i)
        x = x*(1-mix_factor) + pred*mix_factor

    axs[1].imshow(torchvision.utils.make_grid(x.detach().cpu(), nrow=8)[0].clip(0, 1), cmap='plasma')
    axs[1].set_title('Generated Samples')

    # check if the folder exists, if exists, clear it. if not, create it
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    else:
        files = glob.glob(f'{save_folder}/*')
        for f in files:
            os.remove(f)

    # save the figure
    if epoch is not None:
        fig.savefig(f'{save_folder}/epoch_{epoch}.png')

# load the MNIST dataset
dataset = torchvision.datasets.MNIST(root="mnist/",
                                      train=True, download=True, 
                                      transform=torchvision.transforms.ToTensor())

# Dataloader (you can mess with batch size)
batch_size = 128
train_dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

# How many runs through the data should we do?
n_epochs = 3

# Create the network
net = UNet2DModel(
    sample_size=28,  # the target image resolution
    in_channels=1,  # the number of input channels, 3 for RGB images
    out_channels=1,  # the number of output channels
    layers_per_block=2,  # how many ResNet layers to use per UNet block
    block_out_channels=(32, 64, 64),  # Roughly matching our basic unet example
    down_block_types=( 
        "DownBlock2D",  # a regular ResNet downsampling block
        "AttnDownBlock2D",  # a ResNet downsampling block with spatial self-attention
        "AttnDownBlock2D",
    ), 
    up_block_types=(
        "AttnUpBlock2D", 
        "AttnUpBlock2D",  # a ResNet upsampling block with spatial self-attention
        "UpBlock2D",   # a regular ResNet upsampling block
      ),
) #<<<
net.to(device)

# Our loss finction
loss_fn = nn.MSELoss()

# The optimizer
opt = torch.optim.Adam(net.parameters(), lr=1e-3) 

# Keeping a record of the losses for later viewing
losses = []

# The training loop
for epoch in range(n_epochs):

    for x, y in train_dataloader:

        # Get some data and prepare the corrupted version
        x = x.to(device) # Data on the GPU
        noise_amount = torch.rand(x.shape[0]).to(device) # Pick random noise amounts
        noisy_x = corrupt(x, noise_amount) # Create our noisy x

        # Get the model prediction
        pred = net(noisy_x, 0).sample #<<< Using timestep 0 always, adding .sample

        # Calculate the loss
        loss = loss_fn(pred, x) # How close is the output to the true 'clean' x?

        # Backprop and update the params:
        opt.zero_grad()
        loss.backward()
        opt.step()

        # Store the loss for later
        losses.append(loss.item())

    # monitoring the training process
    every_epoch = 1
    if epoch % every_epoch == 0:
        print(f'Loss: {loss.item()}')
        # save the monitoring figure
        monitoring(losses, net, save_folder='monitor', epoch=epoch)


    # Print our the average of the loss values for this epoch:
    avg_loss = sum(losses[-len(train_dataloader):])/len(train_dataloader)
    print(f'Finished epoch {epoch}. Average loss for this epoch: {avg_loss:05f}')




