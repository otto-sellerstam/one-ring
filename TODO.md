# one-ring TODOs

I don't want to add these as issues, as they're more of my own personal notes regarding project development, and features to add (so I don't forget).

## Add multithreading support

The Cython `liburing` wrapper holds the GIL during `waitng_cqe`, which means that other threads cannot run. Two potential fixes include:

### 1. Fork `liburing`

Add code to release the GIL

### 2. Use Eventfd

Don't call `wait_cqe`, but instead register the ring for eventfd, using

```python
io_uring_register_eventfd(ring: io_uring, fd: int) -> int
```

## Implement flag wrappers

The majority of all `liburing` calls take flags of different types. For both type safety, and utility, these flags should be wrapped in custom classes an exposed to be used by low level coroutines and the event loop. For example, `liburing.queue.io_uring_prep_cancel64` takes the following flags:

```
- IORING_ASYNC_CANCEL_ALL
- IORING_ASYNC_CANCEL_ANY
- IORING_ASYNC_CANCEL_FD
- IORING_ASYNC_CANCEL_FD_FIXED
- IORING_ASYNC_CANCEL_OP
- IORING_ASYNC_CANCEL_USERDATA
- IORING_OP_ASYNC_CANCEL
- IORING_REGISTER_SYNC_CANCEL
```

## Improve project directory structure

Once more functionality has been added, structure the project for a clear separation of concerns and functionality from an API point of view.


## Solve inline TODOs

Simply check and fix the inline TODOs in the project.
