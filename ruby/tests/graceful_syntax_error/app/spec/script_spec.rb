require_relative '../script.rb'

describe 'halve' do
    it 'divides its argument by 2' do
        expect(halve(4)).to eq(2)
    end

    it 'errors on non-number inputs' do
        expect{halve("4")}.to raise_error(ArgumentError)
    end

    it 'does not error on integer inputs' do
        expect(halve(8)).to_not raise_error
    end

    it 'can be called by another test' do
        var = halve(6)
        expect(val).to eq(3)
    end
end
