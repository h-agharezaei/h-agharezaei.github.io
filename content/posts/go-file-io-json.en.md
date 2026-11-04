+++
date = '2026-12-06T10:00:00+03:30'
draft = false
title = 'Files, io.Reader/Writer and JSON in Go'
description = 'Go file I/O and JSON: read and write files with os and bufio, see how io.Reader and io.Writer compose, and use encoding/json, with real error messages.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "json", "io"]
cover = { image = "/images/covers/go-file-io-json.png", alt = "Files, io.Reader/Writer and JSON in Go", hiddenInSingle = true }
+++

Suppose you write a function that prints a report. Today it prints to the terminal. Tomorrow someone wants the same report saved in a file, and the day after you want to check its text in a test, without touching the disk. If the function was written to talk to the terminal, you must change it every time, or copy it.

Go avoids this with a very small idea. Instead of "write to the terminal" or "write to this file", the function says "write to anything that can accept bytes". That "anything" is an interface called `io.Writer`, and its twin for reading is `io.Reader`. Once you see them, files, in-memory buffers, network connections and standard output all look the same, and the same code works on all of them.

After [tests and benchmarks](/posts/go-testing-basics/), this post covers the two things real programs do all the time: read and write files, and speak JSON. We start with whole files, then meet the two interfaces, and then use them with the `encoding/json` package.

> I ran everything below with Go 1.27 on an arm64 Mac. All files live in a directory made with `os.MkdirTemp` (named `dir` in the snippets) and removed at the end. Outputs are copied from the run. The code is a local example, not a published repo.

## Whole files and line by line

For a small file the simplest way is to write it in one call and read it back in one call:

```go
path := filepath.Join(dir, "notes.txt")
os.WriteFile(path, []byte("alpha\nbeta\ngamma\n"), 0o644)
data, err := os.ReadFile(path)
fmt.Printf("ReadFile: %q (%d bytes)\n", data, len(data))
```

```text
ReadFile: "alpha\nbeta\ngamma\n" (17 bytes)
```

`filepath.Join` builds a path with the right separator for the operating system. `0o644` is the file permission mode (the owner can read and write, everybody else can read). The output shows that we got back exactly what we wrote: three words, each followed by a newline, 17 bytes in total. `%q` prints the string in quotes with `\n` visible, which is handy when you care about invisible characters.

Reading a file that does not exist returns an error, and `os.IsNotExist(err)` was `true` in my run. (`errors.Is(err, fs.ErrNotExist)` also works.)

`ReadFile` loads the whole file into memory. That is fine for a small config file but wasteful for a big log. For big files, open the file and read it a line at a time with a `bufio.Scanner`. The name comes from "buffered I/O": instead of asking the operating system for every byte, it reads a chunk at once and hands you pieces from it. We close the file with `defer`, as in [functions, defer and errors](/posts/go-functions-defer-errors/):

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

Each call to `sc.Scan()` moves to the next line and returns `true`, and `sc.Text()` gives that line without the newline. Always check `sc.Err()` after the loop: `Scan` returns `false` both at the end of the file and when something goes wrong, and only `Err` tells you which one it was.

Notice that `bufio.NewScanner(f)` accepted a file. It would accept other things too. Let us see why.

## io.Reader and io.Writer

Both interfaces have exactly one method:

```go
type Reader interface { Read(p []byte) (n int, err error) }
type Writer interface { Write(p []byte) (n int, err error) }
```

A `Reader` is "something you can take bytes from": `Read` fills the slice `p` and says how many bytes it put there. A `Writer` is "something you can give bytes to". Many types in the standard library have these methods: `*os.File` has both, and so do `*bytes.Buffer` (a growable in-memory buffer), the value from `strings.NewReader` (it reads from a string) and `os.Stdout`.

So a function that takes an `io.Writer` does not care where the bytes go. Here is the report function from the beginning:

```go
func report(w io.Writer, name string, n int) error {
	_, err := fmt.Fprintf(w, "report %s: %d items\n", name, n)
	return err
}
```

`fmt.Fprintf` is `Printf` with a destination: it formats the text and writes it to `w`. I called `report` three times, with a file, a buffer and `os.Stdout`:

```text
file got: "report file: 3 items\n"
buffer got: "report buffer: 3 items\n"
report stdout: 3 items
```

Same function, same code, three destinations. The first line is what I read back from the file after writing, the second is the content of the buffer, and the third was printed straight to the terminal. This is also why the function is easy to test: in a test you pass a `bytes.Buffer` and compare its string with what you expect, with no files involved.

The standard library also gives you `io.Copy(dst, src)`, which connects any reader to any writer and moves all the bytes:

```go
n, _ := io.Copy(os.Stdout, strings.NewReader("copied from a string\n"))
```

```text
copied from a string
io.Copy bytes: 21
```

It copied the 21 bytes of the string to the terminal and told us how many it moved. `fmt.Fprintf`, `bufio.NewScanner` and, as we are about to see, `json.NewEncoder` all take these interfaces, which is why they plug into each other like pieces of a pipe.

## JSON with struct tags

JSON is the format most programs use to exchange data. The `encoding/json` package converts between Go values and JSON text. Turning a Go value into JSON is called **marshaling**, and the reverse is **unmarshaling**.

Go structs have fields like `Name`, but JSON keys are usually lowercase. A **struct tag**, the backquoted string after a field, tells the package which key to use:

```go
type User struct {
	Name     string   `json:"name"`
	Age      int      `json:"age"`
	Email    string   `json:"email,omitempty"`
	Tags     []string `json:"tags,omitempty"`
	password string
}
```

Two things here are worth knowing. `omitempty` means "leave this key out when the field has its zero value" (an empty string, `0`, an empty or nil slice). And `password` starts with a lowercase letter, so it is unexported, and `encoding/json` can only see exported fields. It will never be written, which is what we want for a secret:

```go
b, _ := json.Marshal(User{Name: "Roham", Age: 30, password: "secret"})
```

```text
{"name":"Roham","age":30}
```

The output has `name` and `age`. `email` and `tags` were left out because of `omitempty`, and `password` because it is unexported. With `Email` and `Tags` set, `json.MarshalIndent(u, "", "  ")` produces readable output with two-space indentation:

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

`json.Unmarshal(b, &u2)` goes the other way. It needs a pointer, because it has to fill your variable. Printing the result with `%+v` (which shows field names) gave `{Name:Roham Age:30 Email:r@example.com Tags:[go backend] password:}`. Everything came back, and `password` stayed empty since it was never in the JSON.

## Streaming with Encoder and Decoder

`json.Marshal` returns a byte slice, which you then have to write somewhere. If you already have a destination, there is a shorter way. `json.NewEncoder(w)` takes any `io.Writer`, and `json.NewDecoder(r)` takes any `io.Reader`. Here is the interface idea paying off.

Each `Encode` call writes one value followed by a newline, so calling it many times gives you a file with one JSON value per line (this is often called JSON Lines). To read it back, call `Decode` in a loop until it returns `io.EOF`, which means the input is finished:

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

Both users came back. `Tags:[]` is just how `%+v` prints a nil slice: the key was absent, so the field kept its zero value. The advantage of this style is that you never hold the whole file in memory, only one value at a time.

## Unknown fields and map[string]any

Real JSON does not always match your struct. By default, a key that the struct does not have is silently ignored. Sometimes you would rather know. A decoder can be switched to strict mode with `DisallowUnknownFields`:

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

The first line is the default behavior: no error, the name was read and `nickname` was dropped. The second is the strict decoder refusing the same input and naming the extra key.

When you do not know the shape of the JSON at all, you can decode into `map[string]any`. It works, but look at what numbers become:

```go
var m map[string]any
json.Unmarshal([]byte(`{"id":7,"name":"x","ok":true,"list":[1,2]}`), &m)
fmt.Printf("%T %v | %T\n", m["id"], m["id"], m["list"])
```

```text
float64 7 | []interface {}
```

`id` was `7` in the JSON, but in Go it is a `float64`, because JSON has just one kind of number. Arrays become `[]any` (which is printed as `[]interface {}`). A float64 cannot hold every large integer exactly, so IDs that are very big can lose precision this way. Prefer a struct when you know the shape.

## What the errors look like

JSON from the outside world is often broken, so it helps to see the error messages. These are from three bad inputs:

```text
syntax: invalid character '}' looking for beginning of object key string
truncated: unexpected end of JSON input
type: json: cannot unmarshal string into Go struct field User.age of type int
```

The first comes from `{"name": "x",}`, which has a trailing comma that JSON does not allow. The second comes from `{"name": "x"`, which is cut off before the closing brace. The third comes from `"age":"thirty"`: the JSON is valid, but a string cannot go into an `int` field, and the message names the field. In my run, after that third error the `Name` field was still filled in (`x`) and `Age` stayed `0`: `Unmarshal` kept going and reported the type mismatch at the end.

## Where errors go silent

- Always `defer f.Close()` right after checking the error from `os.Open`, and check `sc.Err()` after a scan loop. Otherwise a failed read looks like a normal end of file.
- `Scanner` has a default limit of 64 KiB per line. A longer line makes the scan stop with an error; for such input, give it a bigger buffer with `sc.Buffer`.
- `encoding/json` skips lowercase (unexported) fields without any error. If a field is mysteriously always empty, check its first letter.
- `Unmarshal` needs a pointer. And remember that numbers in a `map[string]any` become `float64`.
- Unknown fields are ignored unless you call `DisallowUnknownFields`. A misspelled key in a config file can pass unnoticed.

## Exercise

1. Write `countLines(r io.Reader) (int, error)` with `bufio.Scanner` and test it with `strings.NewReader`.
2. Save a slice of `User` to a file with `json.NewEncoder`, then load it back with `json.NewDecoder`.
3. Add a field `Nickname` with the tag `json:"-"` and see what happens.

## What's next

"Building a command-line tool in Go": files, `io.Reader`, `io.Writer` and JSON are exactly the pieces that post puts together into a command-line tool.
