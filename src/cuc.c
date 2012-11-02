/* (C) 2012 Pedro I. López <dreilopz@gmail.com>
 * This source code is released under the new BSD license, a copy of the
 * license is in the distribution directory.
 */

// Configuration and names --------------------------------------------
#define DELAY   400.0
#define F_CPU   4000000L
#define USART_BAUDRATE 9600
#define BAUD_PRESCALE (((F_CPU / (USART_BAUDRATE * 16UL))) - 1)

#define STATUS  PC5
#define STATUS_CONFIG   DDRC |= _BV(DDC5)
#define STATUS_TOGGLE   PORTC ^= _BV(STATUS)
#define STATUS_OFF      PORTC &= ~_BV(STATUS)
#define STATUS_ON       PORTC |= _BV(STATUS)

#define START '\x00'
#define ACK '\x03'
#define OK_STATUS '\x06'
#define ERROR   '\x0a'
#define END '\x04'

#define READ '\x01'
#define WRITE   '\x0c'
#define REPORT_STATUS '\x07'

#define DISTANCE_SAMPLE '\x02'
#define ADC0_SAMPLE '\x05'
#define OPMODE    '\x0b'

#define NORMAL_MODE         '\x08'
#define NORMAL_MODE_DELAY   500
#define SERIAL_MODE         '\x09'
#define SERIAL_MODE_DELAY   150
// --------------------------------------------------------------------

#include <avr/io.h>
#include <util/delay.h>
#include <avr/interrupt.h>

void ioinit(void);
void set_distance(void);
unsigned int ADC0_value(void);
void TIMER1_off(void);
void TIMER1_on(void);
void signal_update(unsigned int timer1_top);
unsigned char ReadUSART(void);
void WriteUSART( unsigned char byte);

volatile unsigned char MODE = NORMAL_MODE;
volatile unsigned int MODE_DELAY = NORMAL_MODE_DELAY;
volatile unsigned int DISTANCE = 0;

ISR(TIMER1_COMPA_vect) {
    set_distance();
    signal_update(DISTANCE);
}

ISR(USART_RX_vect)
{
    unsigned char rx_byte;
    unsigned int b16;

    rx_byte = ReadUSART();

    if ( rx_byte != START ) {
        WriteUSART(ERROR);
        return;
    }

    WriteUSART(ACK);
    rx_byte = ReadUSART();

    switch ( rx_byte ) {
        case REPORT_STATUS:
            WriteUSART('\x01');
            WriteUSART(OK_STATUS);
            break;

        case READ:
            rx_byte = ReadUSART();
            switch ( rx_byte ) {
                case OPMODE:
                    WriteUSART('\x01');
                    WriteUSART(MODE);
                    break;

                case DISTANCE_SAMPLE:
                    b16 = DISTANCE;
                    WriteUSART('\x02');
                    WriteUSART( (unsigned char) b16 );
                    WriteUSART( (unsigned char) (b16 >> 8) );
                    break;

                case ADC0_SAMPLE:
                    b16 = ADC0_value();
                    WriteUSART('\x02');
                    WriteUSART( (unsigned char) b16 );
                    WriteUSART( (unsigned char) (b16 >> 8) );
                    break;

                default:
                    break;
            }
            break;

        case WRITE:
            rx_byte = ReadUSART();
            switch ( rx_byte ) {
                case OPMODE :
                    MODE = ReadUSART();

                    switch ( MODE ) {
                        case SERIAL_MODE :
                            MODE_DELAY = SERIAL_MODE_DELAY;
                            break;
                        case NORMAL_MODE :
                            MODE_DELAY = NORMAL_MODE_DELAY;
                            break;
                        default:
                            break;
                    }

                    break;

                default:
                    break;

            }
            WriteUSART('\x00');
            break;

        default:
            break;
    }

    if ( ReadUSART() != ACK ) {
        WriteUSART(ERROR);
    }

    if ( ReadUSART() == END ) {
        WriteUSART(ACK);
    }
}

    unsigned char
ReadUSART(void) {
    unsigned char byte;

    while ( !(UCSR0A & _BV(RXC0)) );
    byte = UDR0;
    return byte;
}

    void
WriteUSART( unsigned char byte) {
    while ( !(UCSR0A & _BV(UDRE0)) );
    UDR0 = byte;
    while ( !(UCSR0A & _BV(TXC0)) );
    return;
}

    void
signal_update(unsigned int timer1_top)
{
    if ( timer1_top > 950 ) {
        TCCR1A &= ~_BV(COM1A0);
        PORTB |= _BV(PB1);
    }
    else {
        TCCR1A |= _BV(COM1A0);

        if ( timer1_top > 700 ) {
            OCR1A = ((timer1_top - 250) * 6) / 5;
        }
        else {
            OCR1A = timer1_top - 250;
        }
    }
}

    void
TIMER1_off(void)
{
    TCCR1B &= ~(_BV(CS12) | _BV(CS11) | _BV(CS10));
}

    void
TIMER1_on(void)
{
    // (CS1 = 0b101) => clock source is f_clkio/1024.  Start timer.
    TCCR1B &= ~_BV(CS11);
    TCCR1B |= (_BV(CS12) | _BV(CS10));
}

    unsigned int
ADC0_value(void)
{
    unsigned int adc_value;

    ADCSRA |= _BV(ADEN);  // Enable ADC.
    ADCSRA |= _BV(ADSC);  // Start conversion.
    while (ADCSRA & _BV(ADSC));  // Wait for result.
    ADCSRA &= ~_BV(ADEN);  // Disable ADC.

    // Value as an ``unsigned int`` from 2 ``unsigned char``s (bytes).
    adc_value = (unsigned int) ADCL;
    adc_value |= (((unsigned int) ADCH) << 8);

    return adc_value;
}

    void
set_distance(void)
{
    DISTANCE = (~(ADC0_value())) & 0x3ff;
}

    void
ioinit (void)
{
    cli();  // disable interrupts globally.

    // UART conf. -------------------------------------------------------------
    // Don't double the USART transmission speed.
    UCSR0A &= ~_BV(U2X0);

    // RX Complete Interrupt Enable.
    UCSR0B |= _BV(RXCIE0);

    // Character size in a frame the Receiver and Transmitter use.
    // UCSZ0 = 0b011, so character size is 8 bit.
    UCSR0B &= ~_BV(UCSZ02);
    UCSR0C |= _BV(UCSZ01) | _BV(UCSZ00);

    // UMSEL0 = 0b00, so USART mode of operation is Asynchronous USART
    UCSR0C &= ~(_BV(UMSEL01) | _BV(UMSEL00));

    // UPM0 = 0b00, so parity is disabled.
    UCSR0C &= ~(_BV(UPM01) | _BV(UPM00));

    // USBS0 = 0, so we use 1 stop bit.
    UCSR0C &= ~_BV(USBS0);

    // Baud rate.
    UBRR0L = BAUD_PRESCALE;
    UBRR0H = (BAUD_PRESCALE >> 8);

    // Turn on the transmitter and receiver.
    UCSR0B |= (_BV(RXEN0) | _BV(TXEN0));
    // ------------------------------------------------------------------------

    // TIMER0 ---------------------------------------------------------
    // Use TIMER0 to produce a simple squarewave on pin PB1/OC1A.
    DDRB |= _BV(DDB1);
    PORTB &= ~_BV(PB1);

    // (OCR0A = ) => waveform frequency is  Hz approx.
    OCR1A = 1000;

    // (COM1A = 0b01) => toggle OC1A on Compare Match.
    TCCR1A &= ~_BV(COM1A1);
    TCCR1A |= _BV(COM1A0);

    // (WGM1 = 0b0100) => (waveform generation mode is Clear Timer on Compare
    // Match, TOP = 0CR1A).
    TCCR1A &= ~(_BV(WGM11) | _BV(WGM10));
    TCCR1B |= _BV(WGM12);
    TCCR1B &= ~_BV(WGM13);

    // (OCIE1A = 1) => TIMER1 Output Compare A Match interrupt enabled.
    TIMSK1 |= _BV(OCIE1A);

    TIMER1_on();
    // ----------------------------------------------------------------

    // STATUS LED. ------------------------------------------------------------
    STATUS_CONFIG;
    // ------------------------------------------------------------------------

    // ADC conf ---------------------------------------------------------------
    // (REFS = 0b00) => AREF is voltage reference.
    ADMUX &= ~(_BV(REFS1) | _BV(REFS0));

    // (ADLAR = 0) => Result is right adjusted.
    ADMUX &= ~_BV(ADLAR);

    // (MUX = 0b00000) => Select ADC0/PC0 channel.
    ADMUX &= ~(_BV(MUX3) | _BV(MUX2) | _BV(MUX1) | _BV(MUX0));

    // (ADATE = 0) => Auto Trigger disabled.
    ADCSRA &= ~_BV(ADATE);

    // (ADIE = 0) => ADC Interrupt disabled.
    ADCSRA &= ~_BV(ADIE);

    // (ADPS = 0b110) => (ADC clock prescaler = 64);
    ADCSRA &= ~_BV(ADPS0);
    ADCSRA |= (_BV(ADPS2) | _BV(ADPS1));

    // Digital input buffers in ADC0 channel is disabled.
    DIDR0 |= _BV(ADC0D);
    // ------------------------------------------------------------------------

    sei();
}

    int
main (void)
{
    ioinit ();

    for (;;) {
        STATUS_TOGGLE;
        _delay_ms(MODE_DELAY);
    }

    return 0;
}
