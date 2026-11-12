// Extra differential cases; compare identical mlir-opt output between revisions.
func.func @same_root_group_plus_one_independent(%ret: memref<1xi8>, %c0: i1, %c1: i1, %c2: i1) -> i1 {
  %a = memref.alloc() : memref<2xi8>
  %v0 = memref.subview %a[0][1][1] : memref<2xi8> to memref<1xi8>
  %v1 = memref.subview %a[1][1][1] : memref<2xi8> to memref<1xi8, strided<[1], offset: 1>>
  %b = memref.alloc() : memref<1xi8>
  %res = bufferization.dealloc (%v0, %v1, %b : memref<1xi8>, memref<1xi8, strided<[1], offset: 1>>, memref<1xi8>) if (%c0, %c1, %c2) retain (%ret : memref<1xi8>)
  return %res : i1
}

// -----

func.func @mixed_unknown_and_known_roots(%unknown: memref<1xi8>, %ret: memref<1xi8>, %condition: i1) -> i1 {
  %a0 = memref.alloc() : memref<1xi8>
  %a1 = memref.alloc() : memref<1xi8>
  %res = bufferization.dealloc (%unknown, %a0, %a1 : memref<1xi8>, memref<1xi8>, memref<1xi8>) if (%condition, %condition, %condition) retain (%ret : memref<1xi8>)
  return %res : i1
}
