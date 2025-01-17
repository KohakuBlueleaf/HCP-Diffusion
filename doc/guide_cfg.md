# Configuration file explanation

This section primarily introduces the training parameter settings in the ```cfgs/train/train_base.yaml``` configuration file.
The configuration file is in the ```yaml``` format, supporting extended syntaxes of ```OmegaConf``` and ```hydra```.

## Training configurations

```yaml
train:
  # Gradient accumulation steps
  # Total batch size batch_size = the sum of the batch sizes of each dataset * Gradient accumulation steps * GPU count
  gradient_accumulation_steps: 1
  
  workers: 4 # The number of processes used for parallel data loading. It can be adjusted based on the number of CPU cores.
  max_grad_norm: 1.0 # Gradient clipping is used to prevent gradient explosion.
  set_grads_to_none: False # Whether to set the gradient to None when resetting it.
  save_step: 100 # Saving model interval 
  log_step: 20 # Logging interval
  
  # The CFG scale for DreamArtist, that 1.0 indicates disable DreamArtist.
  # DreamArtist supports dynamic CFG, which varies dynamically with the diffusion time steps. 
  # It format is as follows: lower-upper:activation function. The default activation function is linear, 
  # while cos is used for the 0-π/2 interval of the cos function and cos2 for the π/2-π interval of the cos function.
  cfg_scale: '1.0' 

  resume: # Continue the previous training, or start a new training by set it to null
    ckpt_path:
      unet: [] # All checkpoint path of unet
      TE: [] # All checkpoint path of text-encoder
      words: {} # All checkpoint path of custom words
    start_step: 0 # Steps at the end of the previous training

  loss: # Loss function configuration
    criterion:
      # Here using the syntax of hydra.utils.installate
      # All modules with the _target_ attribute will be instantiated as the corresponding python object
      _target_: torch.nn.MSELoss # Loss function class
      reduction: 'none' # support for attention mask
    # The weight of the loss of the data from data_class
    # Make data.batch_size/(data_class.batch_size*prior_loss_weight) = 4/1 can get better results
    prior_loss_weight: 1.0 
    type: 'eps'

  optimizer: # Optimizer for model parameters 
    type: adamw # optimizer type: [adamw, adamw_8bit, deepspeed]
    weight_decay: 1e-3
    weight_decay_pt: 5e-4 # for word embeddings

  scale_lr: True # Whether to automatically scale the learning rate by total batch size
  scheduler: # Learning rate adjustment strategies, see next section for options
    name: 'one_cycle' # scheduler type
    num_warmup_steps: 200 # Learning rate progressively increasing steps
    num_training_steps: 1000 # Total train steps
    scheduler_kwargs: {} # Other parameters for scheduler

  scale_lr_pt: True # Whether to automatically scale the learning rate of word training by total batch size
  scheduler_pt: ${.scheduler} # Learning rate adjustment strategy for word training. OmegaConf syntax, consistent with scheduler content above
```

## Learning rate adjustment strategy

![](../imgs/lr.webp)

The figure shows the changes in learning rate strategy with steps, and the recommended strategies are ```one_cycle``` or ```constant_with_warmup```. 
The ascending part of the learning rate is set by ```num_warmup_steps```, and the total number of steps is set by ```num_training_steps```.

```one_cycle``` can be adjusted by the following two parameters, which can be written into the ```scheduler_kwargs```:
+ div_factor: max_lr/initial_lr
+ final_div_factor: max_lr/end_lr

## Model configurations

```yaml
model:
  revision: null # revision of pretrainedmodel
  pretrained_model_name_or_path: null # pretrained model name or path
  tokenizer_name: null # The tokenizer can be specified individually
  tokenizer_repeats: 1 # Expand the sentence length by N times, if the caption exceeds the upper limit you can increase the tokenizer_repeats
  enable_xformers: True # enable xformers
  gradient_checkpointing: True # Enable optimization to save VRAM
  ema_unet: 0 # The hyperparameter of the unet ema model, 0 to disable. Usually set to 0.9995
  ema_text_encoder: 0 # Hyperparameters of the text-encoder ema model
  clip_skip: 0 # Skip the last N layers of text-encoder, the value of 0 is consistent with webui's clip_skip=1
```

## Dataset configurations

```yaml
data:
  batch_size: 4 # batch_size of this part of the data
  # prompt template, the fill word is configured in the following utils.caption_tools.TemplateFill
  prompt_template: 'prompt_tuning_template/name.txt'
  caption_file: null # Image caption file path
  cache_latents: True # Whether pre-encoding the image with VAE, which can speed up the training
  att_mask: null # path to attention_mask
  att_mask_encode: False # Whether to apply self-attention in VAE to attention_mask
  bg_color: [255, 255, 255] # Fill background color when reading transparent images
  image_transforms: # Image augmentation and preprocessing, see torchvision.transforms for details
    _target_: torchvision.transforms.Compose # Compose multi transforms
    transforms:
      - _target_: torchvision.transforms.ToTensor
      - _target_: torchvision.transforms.Normalize
        _args_: [[0.5], [0.5]]
  tag_transforms: # Text augmentation and preprocessing
    _target_: torchvision.transforms.Compose
    transforms:
      - _target_: hcpdiff.utils.caption_tools.TagShuffle # Shuffle the caption by ","
      - _target_: hcpdiff.utils.caption_tools.TagDropout # Split the caption by "," and random delete
        p: 0.1 # Probability of deletion
      - _target_: hcpdiff.utils.caption_tools.TemplateFill # Fill the prompt template, randomly choice one line in template to fill
        word_names:
          pt1: pt-cat1 # Replace {pt1} in the template with pt-cat1
          class: cat # Replace {class} in the template with cat
  bucket: # What bucket to use for image processing and grouping
    _target_: hcpdiff.data.bucket.RatioBucket.from_files # Automatic clustering and grouping of all images in aspect ratio, avoiding crop as much as possible
    img_root: 'imgs/train' # images path
    # Image size used for training, value is area
    # Here we use the hydra syntax and call python's eval function to calculate the area
    target_area: {_target_: "builtins.eval", _args_: ['512*512']}
    num_bucket: 5 # The number of groups
#  bucket:
#    _target_: data.bucket.FixedBucket # Resize and crop images to fixed size
#    img_root: 'imgs/train'
#    target_size: [512, 512]
```

The settings in ``data_class`` are the same as above.

## Other configurations
```yaml
# Parent configuration file to inherite, which modifies the parameters of the parent file, can inherit multiple files.
# Only the parameters that have been modified need to be written, while the default values of the other parameters will be used.
# The list will be entirely replaced and cannot modify one item, so it is necessary to write them completely.
_base_: [cfgs/train/train_base.yaml, cfgs/train/tuning_base.yaml]

exp_dir: exps/ # Output folder
mixed_precision: 'fp16' # Whether to use half-precision training acceleration
seed: 114514 # Random seeds for training
ckpt_type: 'safetensors' # [torch, safetensors], save torch or safetensors format
```