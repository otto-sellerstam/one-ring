# one-ring TODOs

I don't want to add these as issues, as they're more of my own personal notes regarding project development, and features to add (so I don't forget).

## Migrate `one-ring-core` into `rusty-ring` (probably)

`one-ring-core` provides a thinn wrapper functionality around `rusty-ring`. If nothing else, it could be implemented as Python functionality inside the package, if not directly into the Rust code.

## Improve project directory structure

Once more functionality has been added, structure the project for a clear separation of concerns and functionality from an API point of view.

## Typed dynamic path and query params into path function signatures (maybe)

Implement FastAPI style support for typed dynamic path variables and query params.

## Solve inline TODOs

Simply check and fix the inline TODOs in the project.
