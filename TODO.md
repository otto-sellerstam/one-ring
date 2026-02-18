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

## Improve project directory structure

Once more functionality has been added, structure the project for a clear separation of concerns and functionality from an API point of view.

## Implement an `execute` function to reduce boilerplate in low-level coroutines

See title eeh

## Solve inline TODOs

Simply check and fix the inline TODOs in the project.
