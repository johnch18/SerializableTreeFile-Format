# Serializable Tree File Format (`STF`) Version a.0.0.3

A tree-based file format. Leaves are primitive types, branches are descendants of STFObject.

## `STFObject`

An `STFObject` is the base of the file format. Subclassing it and implementing the abstract data members makes the type
in question able to be serialized.

### `STFObject.deserialize`

Converts bytes into the requisite object

### `STFObject.data`

Converts an object into bytes

### `STFObject.metadata`

Allows you to encode more information, I for instance used this for STFArray to encode the length of the array.

## `STFArray`

Basically an array of identically typed objects that are serialized as an array. All you need to do to use it is make a
class level variable called `T` pointing to the type you're storing.

