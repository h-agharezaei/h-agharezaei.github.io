+++
date = '2026-11-16T18:00:00+03:30'
draft = false
title = 'Testing, fuzzing and invariants with Foundry'
description = 'Foundry tests in Solidity: unit tests with cheatcodes, bounded fuzz tests, an invariant test with a handler that finds a planted bug, gas and coverage.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "foundry", "testing", "fuzzing"]
cover = { image = "/images/covers/bc-foundry-testing-fuzzing.png", alt = "Testing, fuzzing and invariants with Foundry", hiddenInSingle = true }
+++

In the last post I tried the vault by hand: a deposit here, a move there, one withdrawal that failed. That felt fine, and it proves almost nothing. I tried maybe five cases. A contract can be called with any amount, from any address, in any order, by anyone on earth. And once it is deployed, you cannot simply patch it: changing a contract after deploy needs extra machinery, and meanwhile it holds other people's money. So tests matter even more here than in a normal backend service.

This post tests the vault from [the previous post](/posts/bc-solidity-first-contract/) with Foundry, and the tests are written in Solidity itself. We go in three steps, from "I check cases I thought of" to "the machine looks for cases I did not think of": unit tests, fuzz tests, and invariant tests.

The ideas are not new to this blog: [Testing in Go: table-driven tests and benchmarks](/posts/go-testing-basics/), [Testing and documentation in Rust](/posts/rust-testing-docs/), [Property-based testing](/posts/eng-property-based-testing/) and [Fuzzing to find security bugs](/posts/sec-fuzzing/) covered them in other languages. What is new here is the cheatcodes and the invariant runner.

> Everything below was run with Foundry 1.8.7 and solc 0.8.38 on macOS (arm64). I copied the previous post's project unchanged (the same `src/Vault.sol`) into a new local folder and only added tests. Fuzz runs are random, so the numbers that depend on them, and the counterexample you get, will differ from mine.

## Unit tests and cheatcodes

A test is a contract. Every function whose name starts with `test` is run by `forge test`, and `setUp` runs before each one, on a fresh state. The test contract deploys its own copy of the vault, so it is the vault's owner:

```solidity
contract VaultTest is Test {
    Vault vault;
    address alice = makeAddr("alice");

    event Deposited(address indexed account, uint256 amount);

    function setUp() public {
        vault = new Vault(); // this test contract is the owner
        vm.deal(alice, 10 ether);
    }

    function test_DepositEmitsEvent() public {
        vm.expectEmit(true, false, false, true, address(vault));
        emit Deposited(alice, 2 ether);
        vm.prank(alice);
        vault.deposit{value: 2 ether}();
    }

    function test_RevertWhen_WithdrawMoreThanBalance() public {
        vm.prank(alice);
        vault.deposit{value: 1 ether}();
        vm.expectRevert(abi.encodeWithSelector(Vault.InsufficientBalance.selector, 1 ether, 2 ether));
        vm.prank(alice);
        vault.withdraw(2 ether);
    }
}
```

Something looks odd: the test pretends to be `alice`, and gives her 10 ether out of thin air. That is what `vm` is for. It is the {{< term "cheatcode" "cheatcode" >}} interface: special calls that the test EVM handles itself, which a real chain would never allow. The ones used here:

- `vm.deal(alice, 10 ether)` sets an account's ETH balance.
- `vm.prank(alice)` makes the **next** call look like it came from `alice`.
- `vm.expectRevert(...)` says the next call must fail, with exactly that error and those arguments. If it succeeds, or fails differently, the test fails.
- `vm.expectEmit(...)` says the next call must emit a certain event. The four booleans tell which parts to compare (three topics and the data), and the last argument says which contract should emit it.

The file also has tests for the owner check and for "paused blocks deposits but not withdrawals". These are ordinary unit tests: each checks one case that I thought of in advance.

## Fuzz tests

Now the question: what about the cases I did not think of? Give a test **parameters**, and it becomes a {{< term "fuzzing" "fuzz" >}} test. Foundry calls it many times (256 by default) with generated inputs, trying to break the assertions. Random numbers are usually huge, though, and a deposit of 10^70 wei just reverts without testing anything. So `bound` maps any `uint256` into a range we choose, which keeps the runs useful:

```solidity
function testFuzz_DepositWithdrawRoundTrip(uint256 amount, uint256 out) public {
    amount = bound(amount, 1, 10 ether);
    out = bound(out, 1, amount);
    vm.startPrank(alice);
    vault.deposit{value: amount}();
    vault.withdraw(out);
    vm.stopPrank();
    assertEq(vault.balanceOf(alice), amount - out);
    assertEq(alice.balance, 10 ether - amount + out);
    assertEq(address(vault).balance, vault.totalDeposits());
}
```

This test states a rule, not a case: "for any deposit and any withdrawal no bigger than it, the vault balance, Alice's wallet and the vault's ETH all add up". There is also `testFuzz_MoveKeepsTotal(address to, uint256 amount)`, which deposits and moves everything to a random `to`, and checks that the sum of the two balances still equals `totalDeposits`.

## An invariant test with a handler

A fuzz test still tests one scenario shape: deposit, then withdraw. Real bugs often need a longer sequence: deposit, move, move, withdraw, in some order. An {{< term "invariant-testing" "invariant test" >}} handles that. It calls random functions in random order, many times, and after every call checks a property that must always be true, the {{< term "invariant" "invariant" >}}.

There is a practical problem. If the fuzzer calls the vault directly with random senders and amounts, nearly every call reverts (the sender has no balance, the amount is too big), and nothing interesting happens. So I put a **handler** in front of the vault: a contract whose functions turn raw random input into valid calls between three fixed actors (alice, bob, carol). Here is `move`:

```solidity
function move(uint256 from, uint256 to, uint256 amount) external {
    address a = actors[from % actors.length];
    address b = actors[to % actors.length];
    uint256 bal = vault.balanceOf(a);
    if (bal == 0) return;
    amount = bound(amount, 1, bal);
    vm.prank(a);
    vault.move(b, amount);
}
```

Random numbers pick two of the three actors, and the amount is bounded by the sender's real balance. `deposit` and `withdraw` in the handler look the same. The test then tells Foundry to call **only** the handler, and states the property. A vault is healthy if every wei it holds is owned by someone, and nobody owns more than it holds:

```solidity
function setUp() public {
    vault = new Vault();
    handler = new VaultHandler(vault);
    targetContract(address(handler)); // only the handler is called
}

function invariant_SolventAndConserved() public view {
    uint256 sum;
    for (uint256 i = 0; i < handler.actorCount(); i++) {
        sum += vault.balanceOf(handler.actors(i));
    }
    assertEq(sum, vault.totalDeposits(), "sum of balances != totalDeposits");
    assertEq(address(vault).balance, vault.totalDeposits(), "ETH held != totalDeposits");
}
```

Running everything:

```
$ forge test
[PASS] testFuzz_DepositWithdrawRoundTrip(uint256,uint256) (runs: 256, μ: 147916, ~: 148416)
[PASS] testFuzz_MoveKeepsTotal(address,uint256) (runs: 256, μ: 160952, ~: 160766)
...
[PASS] invariant_SolventAndConserved() (runs: 256, calls: 128000, reverts: 0)
Ran 2 test suites in 12.55s (12.57s CPU time): 8 tests passed, 0 failed, 0 skipped (8 total tests)
(trimmed)
```

For a fuzz test, `runs: 256` is the number of generated inputs, `μ` the mean gas and `~` the median. The invariant line says forge made 128,000 calls (256 runs of 500 calls each) with zero reverts. That last number is the important one: it tells us the handler produces valid calls, so the fuzzer spends its time on interesting states and not on rejections. (The timings and gas figures of fuzz runs differ a little from run to run.)

## Plant a bug, let the fuzzer find it

All green. But green only means something if the tests can go red. So I wrote a bug on purpose, the kind a well-meaning developer might write while "saving an SLOAD" (a storage read) in `move`:

```solidity
uint256 toBal = balanceOf[to]; // "save an SLOAD" refactor (planted bug)
balanceOf[msg.sender] = bal - amount;
balanceOf[to] = toBal + amount;
```

It reads the receiver's balance first, subtracts from the sender, then writes the old receiver balance plus the amount. That is fine unless sender and receiver are the same person: then the second write uses the old balance and the subtraction is lost. Moving money to yourself mints money. I planted this in a scratch copy of the project and ran the tests:

```
$ forge test
Suite result: ok. 7 passed; 0 failed; 0 skipped; finished in 8.67ms (17.06ms CPU time)

[FAIL: sum of balances != totalDeposits: 15484560494319151770 != 15484560494319151755]
	[Sequence] (original: 15, shrunk: 2)
		sender=0x95Ff13e58c51Bc36a7cD2ba8CE27372e941BECd6 addr=[test/handlers/VaultHandler.sol:VaultHandler]0x2e234DAe75C793f67A35089C9d99245E1C58470b calldata=deposit(uint256,uint256) args=[687, 0]
		sender=0x00000000000000000000000000000000000008B9 addr=[test/handlers/VaultHandler.sol:VaultHandler]0x2e234DAe75C793f67A35089C9d99245E1C58470b calldata=move(uint256,uint256,uint256) args=[0, 0, 15]
 invariant_SolventAndConserved() (runs: 1, calls: 15, reverts: 0)
(trimmed)
```

- **`7 passed`:** every unit and fuzz test is still green. Even `testFuzz_MoveKeepsTotal`, which moves money to a random `to`, did not notice: a random address essentially never equals `alice`, so the self-move case was never tried.
- **`FAIL: sum of balances != totalDeposits`:** the invariant broke in the very first run. The two numbers differ by 15: exactly the amount that was moved.
- **`original: 15, shrunk: 2`:** the failing sequence had 15 calls. Foundry then {{< term "shrinking" "shrank" >}} it, throwing away calls that do not matter, until the smallest sequence that still fails was left.
- **The two calls:** actor 0 deposits, then actor 0 moves 15 to actor 0 (`move` arguments `[0, 0, 15]`: from 0, to 0, amount 15). That is the bug in two lines. Since the handler picks among only three actors, it hits a self-move quickly.

The counterexample is random, so yours will have other numbers. Once the bug is clear, the fix is the original `balanceOf[to] += amount;` after the subtraction. The habit I recommend: first turn the counterexample into a plain unit test, and check that it fails with the bug and passes without it. I did that with numbers from an earlier run of mine, and with the bug in place it fails with `assertion failed: 6545 != 5659`:

```solidity
function test_MoveToSelfKeepsBalance() public {
    vm.startPrank(alice);
    vault.deposit{value: 5659}();
    vault.move(alice, 886);
    vm.stopPrank();
    assertEq(vault.balanceOf(alice), 5659);
}
```

6545 is 5659 + 886: the minted amount, exactly. This test stays in the project forever, so nobody can bring the bug back unnoticed.

## Gas report and coverage

Two more reports come free with forge. First, `--gas-report` shows how much gas each function used across all test calls:

```
$ forge test --match-contract VaultTest --gas-report
| Function Name                | Min             | Avg   | Median | Max   | # Calls |
| balanceOf                    |            2869 |  2869 |   2869 |  2869 |     773 |
| deposit                      |           23489 | 69663 |  69752 | 69752 |     520 |
| move                         |           32339 | 54103 |  54239 | 54311 |     258 |
| setPaused                    |           23813 | 25951 |  25951 | 28090 |       2 |
| totalDeposits                |            2425 |  2425 |   2425 |  2425 |     515 |
| withdraw                     |           24220 | 40922 |  40982 | 41030 |     259 |
(trimmed)
```

The deposit median (69,752) is the same number anvil's receipt showed in the last post, and withdraw's minimum, 24,220, equals the gas of the reverted withdraw there. These are gas units, which are deterministic, not time. The averages for fuzzed functions move slightly between runs.

Second, `forge coverage` shows which parts of the code the tests actually executed:

```
$ forge coverage
| File                           | % Lines         | % Statements   | % Branches    | % Funcs        |
| src/Vault.sol                  | 100.00% (30/30) | 80.65% (25/31) | 25.00% (2/8)  | 100.00% (7/7)  |
| test/handlers/VaultHandler.sol | 92.86% (26/28)  | 96.30% (26/27) | 100.00% (2/2) | 80.00% (4/5)   |
(trimmed)
```

{{< term "code-coverage" "Coverage" >}} works with forge (it printed a warning that it turns the optimizer off to get accurate numbers). Every line of the vault ran, but only 2 of 8 branches did. A branch here is each side of an `if`, and the missing ones are the error paths. `forge coverage --report debug` lists them: `revert ZeroAmount()` has zero hits, which is true, because no test sends a zero amount. It also shows `revert IsPaused()` with zero hits, even though one test reaches it inside `vm.expectRevert`; I did not dig into why the report does not count it. I read the branch number as a list of questions to ask, not as a grade.

## Fuzzing and invariant traps

- **Prefer `bound` to `vm.assume` for ranges.** `assume` throws away inputs that do not fit, and if too many are thrown away the test fails for lack of data. `bound` maps every input into the range instead.
- **A handler that reverts most of the time tests nothing.** Always look at the `reverts` number.
- **Random addresses almost never collide with your actors.** Cases like a self-transfer or the same sender and receiver must be put in on purpose, as the planted bug showed.
- **Turn every counterexample into a unit test before fixing the bug.** Otherwise the fix works only until the next random run.

## Exercise

1. Add `test_RevertWhen_ZeroDeposit` and `test_RevertWhen_ZeroWithdraw` and rerun coverage. Which branches turn green?
2. Plant a different bug in `withdraw`: forget `totalDeposits -= amount`. Which assertion in the invariant fails first?
3. Add a fourth actor that is a contract which rejects ETH, and a `withdraw` for it in the handler. What does the invariant say?

## What's next

The next post is "Tokens: ERC-20 and ERC-721". The vault kept balances for one purpose; tokens turn "a ledger of balances" into a standard that every wallet and exchange understands, and we build them with the same project and tools.
