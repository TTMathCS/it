(module
  (import "env" "show" (func $show (param i32)))
  (func (export "add") (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add
    call $show
    local.get $a
    local.get $b
    i32.add))
