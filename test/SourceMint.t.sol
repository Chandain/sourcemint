// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import { Test, console } from "forge-std/Test.sol";
import { SourceMint } from "../src/SourceMint.sol";

contract SourceMintTest is Test {
    SourceMint token;

    uint256 constant INITIAL_SUPPLY = 1_000_000 ether;
    address alice = address(0xA11CE);
    address bob = address(0xB0B);
    address user = address(0x1234);

    function setUp() public {
        token = new SourceMint(INITIAL_SUPPLY);
    }

    function test_NoMintFunction() public {
        bytes4 selector = bytes4(keccak256("mint(address,uint256)"));
        bytes memory data = abi.encodeWithSelector(selector, user, 100);

        (bool s, ) = address(token).call(data);

        assertFalse(s);
    }

    function test_NoSetFeeFunction() public {
        (bool s, ) = address(token).call(abi.encodeWithSignature("setFee(uint256)", 100));

        assertFalse(s);
    }

    function test_NoPauseFunction() public {
        (bool s, ) = address(token).call(abi.encodeWithSignature("pause()"));

        assertFalse(s);
    }

    function test_NoOwnerFunction() public {
        (bool s, ) = address(token).call(abi.encodeWithSignature("owner()"));

        assertFalse(s);
    }

    function test_Metadata() public view {
        assertEq(token.name(), "SourceMint");
        assertEq(token.symbol(), "SRCMNT");
        assertEq(token.decimals(), 18);
    }

    function test_InitialSupplyMintedToDeployer() public view {
        assertEq(token.totalSupply(), INITIAL_SUPPLY);
        assertEq(token.balanceOf(address(this)), INITIAL_SUPPLY);
    }

    function test_Transfer() public {
        token.transfer(alice, 100 ether);
        assertEq(token.balanceOf(alice), 100 ether);
        assertEq(token.balanceOf(address(this)), INITIAL_SUPPLY - 100 ether);

        vm.prank(alice);
        token.transfer(bob, 40 ether);
        assertEq(token.balanceOf(bob), 40 ether);
        assertEq(token.balanceOf(alice), 60 ether);
    }

    function test_BurnReducesSupply() public {
        token.transfer(alice, 50 ether);

        vm.prank(alice);
        token.burn(10 ether);

        assertEq(token.balanceOf(alice), 40 ether);
        assertEq(token.totalSupply(), INITIAL_SUPPLY - 10 ether);
    }
}
