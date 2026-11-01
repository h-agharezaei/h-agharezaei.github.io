+++
date = '2027-06-27T10:00:00+03:30'
draft = false
title = 'Testing, fuzzing and invariants with Foundry'
description = 'Foundry tests in Solidity: unit tests with cheatcodes, bounded fuzz tests, an invariant test with a handler that finds a planted bug, gas and coverage.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "solidity", "foundry", "testing", "fuzzing"]
cover = { image = "/images/covers/bc-foundry-testing-fuzzing.png", alt = "Testing, fuzzing and invariants with Foundry", hiddenInSingle = true }
+++

In [A first contract with Solidity and Foundry](/posts/bc-solidity-first-contract/) I deployed a small ETH vault and poked it with `cast`. A contract cannot be patched after deploy without extra machinery, and it holds money, so tests matter more than in a backend service. This post tests that vault with Foundry, in Solidity.

The ideas are the ones from [Testing in Go: table-driven tests and benchmarks](/posts/go-testing-basics/), [Testing and documentation in Rust](/posts/rust-testing-docs/), [Property-based testing](/posts/eng-property-based-testing/) and [Fuzzing to find security bugs](/posts/sec-fuzzing/). What is new is the cheatcodes and the invariant runner.

> Foundry 1.8.7, solc 0.8.38, macOS (arm64). I copied the previous post's project unchanged (same `src/Vault.sol`) into a new local folder and only added tests. Fuzz runs are random, so your counterexample will differ.

## Unit tests and cheatcodes

A test is a contract whose `test*` functions `forge test` calls. `setUp` runs before each one, on a fresh state:

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

`vm` is the {{< term "cheatcode" "cheatcode" >}} interface: calls the test EVM handles itself. `vm.deal` sets an ETH balance, `vm.prank` makes the next call come from `alice`, `vm.expectRevert` expects the next call to fail with exactly that error and arguments, and `vm.expectEmit` checks the next event (the booleans say which topics and the data to compare). The file also has tests for the owner check and for "paused blocks deposits but not withdrawals".

## Fuzz tests

A test with parameters is a {{< term "fuzzing" "fuzz" >}} test: forge calls it 256 times by default with generated inputs. `bound` maps any `uint256` into a range, which keeps runs useful instead of reverting:

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

There is also `testFuzz_MoveKeepsTotal(address to, uint256 amount)`, which deposits and moves everything to a random `to`.

## An invariant test with a handler

An {{< term "invariant-testing" "invariant test" >}} calls random functions in random order, then checks a property after each call. Calling the vault directly with random senders and amounts mostly reverts, so I put a handler in front of it that turns raw input into valid calls between three actors:

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

`deposit` and `withdraw` look the same. The test targets only the handler and states the vault's {{< term "invariant" "invariant" >}}:

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

```
$ forge test
[PASS] testFuzz_DepositWithdrawRoundTrip(uint256,uint256) (runs: 256, μ: 147559, ~: 148410)
[PASS] testFuzz_MoveKeepsTotal(address,uint256) (runs: 256, μ: 160902, ~: 160345)
...
[PASS] invariant_SolventAndConserved() (runs: 256, calls: 128000, reverts: 0)
Ran 2 test suites in 11.92s (11.95s CPU time): 8 tests passed, 0 failed, 0 skipped (8 total tests)
(trimmed)
```

128,000 calls and zero reverts: the handler is doing its job.

## Plant a bug, let the fuzzer find it

Now a "save an SLOAD" refactor of `move` that I wrote on purpose:

```solidity
uint256 toBal = balanceOf[to]; // "save an SLOAD" refactor (planted bug)
balanceOf[msg.sender] = bal - amount;
balanceOf[to] = toBal + amount;
```

When `to == msg.sender`, the second write uses the old balance and the subtraction is lost. Moving to yourself mints money.

```
$ forge test
Suite result: ok. 7 passed; 0 failed; 0 skipped; finished in 8.59ms (16.11ms CPU time)

[FAIL: sum of balances != totalDeposits: 10263 != 9377]
	[Sequence] (original: 10, shrunk: 2)
		sender=0x00000000000000000000000000000000000000A3 addr=[test/handlers/VaultHandler.sol:VaultHandler]0x2e234DAe75C793f67A35089C9d99245E1C58470b calldata=deposit(uint256,uint256) args=[0, 5659]
		sender=0x00000000000000000000000000000000000022Ea addr=[test/handlers/VaultHandler.sol:VaultHandler]0x2e234DAe75C793f67A35089C9d99245E1C58470b calldata=move(uint256,uint256,uint256) args=[0, 0, 886]
 invariant_SolventAndConserved() (runs: 1, calls: 10, reverts: 0)
(trimmed)
```

The invariant broke in the first run, and {{< term "shrinking" "shrinking" >}} cut ten calls to two: actor 0 deposits, then moves 886 to actor 0. The gap, 10263 − 9377, is exactly 886. The unit suite above, including the fuzz test that moves to a random `to`, passed: in 256 runs a random address never equalled `alice`. The handler, choosing among three actors, hit it at once.

The fix is the original `balanceOf[to] += amount;` after the subtraction. I added the counterexample as a plain unit test, checked that it fails with the bug (`assertion failed: 6545 != 5659`) and passes without it:

```solidity
function test_MoveToSelfKeepsBalance() public {
    vm.startPrank(alice);
    vault.deposit{value: 5659}();
    vault.move(alice, 886);
    vm.stopPrank();
    assertEq(vault.balanceOf(alice), 5659);
}
```

## Gas report and coverage

```
$ forge test --match-contract VaultTest --gas-report
| Function Name                | Min             | Avg   | Median | Max   | # Calls |
| balanceOf                    |            2869 |  2869 |   2869 |  2869 |     773 |
| deposit                      |           23489 | 69663 |  69752 | 69752 |     520 |
| move                         |           32339 | 54114 |  54299 | 54311 |     258 |
| setPaused                    |           23813 | 25951 |  25951 | 28090 |       2 |
| totalDeposits                |            2425 |  2425 |   2425 |  2425 |     515 |
| withdraw                     |           24220 | 40917 |  40958 | 41030 |     259 |
(trimmed)
```

The deposit median matches anvil's receipt from the last post (69,752), and withdraw's minimum, 24,220, is the same as the reverted withdraw there. These are gas units, deterministic, not time.

```
$ forge coverage
| File                           | % Lines         | % Statements   | % Branches    | % Funcs        |
| src/Vault.sol                  | 100.00% (30/30) | 80.65% (25/31) | 25.00% (2/8)  | 100.00% (7/7)  |
| test/handlers/VaultHandler.sol | 92.86% (26/28)  | 96.30% (26/27) | 100.00% (2/2) | 80.00% (4/5)   |
(trimmed)
```

{{< term "code-coverage" "Coverage" >}} worked (forge warned that it turns the optimizer off). 100% of lines, 25% of branches. `--report debug` lists `revert ZeroAmount()` with zero hits: true, no test sends zero. It also lists `revert IsPaused()` with zero hits, although a test reaches it under `vm.expectRevert`; I did not dig into why. I read the branch number as a list of questions, not a grade.

## A few things to watch

- `bound` beats `vm.assume` for ranges: assume throws inputs away, and too many rejects fail the test.
- A handler that reverts most of the time tests nothing. Watch the `reverts` column.
- Random addresses almost never collide with your actors. Put aliasing cases (self-transfer, same sender and receiver) in on purpose.
- Turn every counterexample into a unit test before fixing.

## Exercise

1. Add `test_RevertWhen_ZeroDeposit` and `test_RevertWhen_ZeroWithdraw` and rerun coverage.
2. Plant a bug in `withdraw`: forget `totalDeposits -= amount`. Which assertion fails first?
3. Add a fourth actor that is a contract rejecting ETH, and a `withdraw` in the handler for it. What does the invariant say?

## What's next

Next post: **Tokens: ERC-20 and ERC-721**.
