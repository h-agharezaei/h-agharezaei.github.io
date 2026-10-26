+++
date = '2026-12-06T10:00:00+03:30'
draft = false
title = 'Files, io.Reader/Writer and JSON in Go'
description = 'Go file I/O and JSON: read and write files with os and bufio, see how io.Reader and io.Writer compose, and use encoding/json, with real error messages.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "json", "io"]
cover = { image = "/images/covers/go-file-io-json.png", alt = "Files, io.Reader/Writer and JSON in Go", hiddenInSingle = true }
+++

In the [previous post](/posts/go-testing-basics/) we wrote tests and benchmarks. Real programs also read files and talk JSON, so this post covers both. The key idea is two tiny interfaces, `io.Reader` and `io.Writer`: once you see them, files, buffers, network connections and standard output all look the same.

> I ran everything below with Go 1.26 on an arm64 Mac. All files live in a directory made with `os.MkdirTemp` (named `dir` in the snippets) and removed at the end. Outputs are copied from the run.

## Whole files and line by line

For small files, two functions are enough:

```go
path := filepath.Join(dir, "notes.txt")
os.WriteFile(path, []byte("alpha\nbeta\ngamma\n"), 0o644)
data, err := os.ReadFile(path)
fmt.Printf("ReadFile: %q (%d bytes)\n", data, len(data))
```

```text
ReadFile: "alpha\nbeta\ngamma\n" (17 bytes)
```

`0o644` is the permission mode. Reading a missing file returns an error, and `os.IsNotExist(err)` was `true` in my run. (`errors.Is(err, fs.ErrNotExist)` also works.)

`ReadFile` loads everything into memory. For big files, open the file and read line by line with a **bufio.Scanner**. Close the file with `defer`, as in the [defer post](/posts/go-functions-defer-errors/):

```go
f, err := os.Open(path)
if err != nil { /* handle */ }
defer f.Close()
sc := bufio.NewScanner(f)
for n := 1; sc.Scan(); n++ {
	fmt.Printf("line %d: %s\n", n, sc.Text())
}
if err := sc.Err(); err != nil { /* handle */ }
```

```text
line 1: alpha
line 2: beta
line 3: gamma
```

Always check `sc.Err()` after the loop: `Scan` returns `false` both at the end and on an error.

## io.Reader and io.Writer

Both interfaces have one method each:

```go
type Reader interface { Read(p []byte) (n int, err error) }
type Writer interface { Write(p []byte) (n int, err error) }
```

`*os.File` implements both. So do `*bytes.Buffer`, the value from `strings.NewReader`, and `os.Stdout`. A function that takes an `io.Writer` does not care where the bytes go:

```go
func report(w io.Writer, name string, n int) error {
	_, err := fmt.Fprintf(w, "report %s: %d items\n", name, n)
	return err
}
```

I called it with a file, a buffer and stdout:

```text
file got: "report file: 3 items\n"
buffer got: "report buffer: 3 items\n"
report stdout: 3 items
```

That is also why this function is easy to test: pass a `bytes.Buffer` and compare the string. `io.Copy(dst, src)` connects any reader to any writer:

```go
n, _ := io.Copy(os.Stdout, strings.NewReader("copied from a string\n"))
```

```text
copied from a string
io.Copy bytes: 21
```

`fmt.Fprintf`, `bufio.NewScanner` and, as we will see, `json.NewEncoder` all take these interfaces, which is why they plug into each other.

## JSON with struct tags

```go
type User struct {
	Name     string   `json:"name"`
	Age      int      `json:"age"`
	Email    string   `json:"email,omitempty"`
	Tags     []string `json:"tags,omitempty"`
	password string
}
```

The **struct tag** sets the JSON key. `omitempty` drops the field when it has its zero value. The unexported `password` is never encoded, because `encoding/json` can only see exported fields:

```go
b, _ := json.Marshal(User{Name: "Roham", Age: 30, password: "secret"})
```

```text
{"name":"Roham","age":30}
```

With `Email` and `Tags` set, `json.MarshalIndent(u, "", "  ")` gives readable output:

```text
{
  "name": "Roham",
  "age": 30,
  "email": "r@example.com",
  "tags": [
    "go",
    "backend"
  ]
}
```

`json.Unmarshal(b, &u2)` goes the other way and needs a pointer. The result printed `{Name:Roham Age:30 Email:r@example.com Tags:[go backend] password:}`: `password` stayed empty.

## Streaming with Encoder and Decoder

`json.NewEncoder(w)` writes to any `io.Writer`, and `json.NewDecoder(r)` reads from any `io.Reader`. Each `Encode` writes one value followed by a newline, which gives you a JSON Lines file:

```go
enc := json.NewEncoder(jf) // jf is an *os.File
enc.Encode(User{Name: "x", Age: 1})
enc.Encode(User{Name: "y", Age: 2})
// later: reopen and decode until io.EOF
dec := json.NewDecoder(jf)
for {
	var v User
	if err := dec.Decode(&v); err == io.EOF {
		break
	} else if err != nil { /* handle */ }
	fmt.Printf("decoded: %+v\n", v)
}
```

```text
decoded: {Name:x Age:1 Email: Tags:[] password:}
decoded: {Name:y Age:2 Email: Tags:[] password:}
```

## Unknown fields and map[string]any

By default, extra keys are silently ignored. A decoder can be told to be strict:

```go
in := `{"name":"Roham","age":30,"nickname":"r"}`
d := json.NewDecoder(strings.NewReader(in))
d.DisallowUnknownFields()
fmt.Println("strict err:", d.Decode(&u3))
```

```text
lenient err: <nil> Roham
strict err: json: unknown field "nickname"
```

When you do not know the shape, decode into `map[string]any`. Note what happens to numbers:

```go
var m map[string]any
json.Unmarshal([]byte(`{"id":7,"name":"x","ok":true,"list":[1,2]}`), &m)
fmt.Printf("%T %v | %T\n", m["id"], m["id"], m["list"])
```

```text
float64 7 | []interface {}
```

`id` is a `float64`, and arrays become `[]any`. Prefer a struct when you can.

## Error messages

```text
syntax: invalid character '}' looking for beginning of object key string
truncated: unexpected end of JSON input
type: json: cannot unmarshal string into Go struct field User.age of type int
```

These come from `{"name": "x",}` (trailing comma), `{"name": "x"` (cut off), and `"age":"thirty"`. The last one is a type mismatch and names the field.

## A few things to watch

- Always `defer f.Close()` right after checking the error from `os.Open`, and check `sc.Err()`.
- `Scanner` has a default line limit of 64 KiB; for longer lines use `sc.Buffer`.
- Lowercase fields are skipped by `encoding/json` without any error.
- `Unmarshal` needs a pointer, and big numbers in `map[string]any` become `float64`.
- Unknown fields are ignored unless you call `DisallowUnknownFields`.

## Exercise

1. Write `countLines(r io.Reader) (int, error)` with `bufio.Scanner` and test it with `strings.NewReader`.
2. Save a slice of `User` to a file with `json.NewEncoder`, then load it back with `json.NewDecoder`.
3. Add a field `Nickname` with the tag `json:"-"` and see what happens.

## What's next

Next we will put these pieces together and build a command-line tool in Go.
