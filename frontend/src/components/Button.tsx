import { forwardRef, type ButtonHTMLAttributes } from 'react';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;

function joinClassNames(...classNames: Array<string | undefined>) {
    return classNames.filter(Boolean).join(' ');
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
    { className, disabled, type = 'button', ...props },
    ref,
) {
    return (
        <button
            ref={ref}
            type={type}
            disabled={disabled}
            className={joinClassNames('cursor-pointer disabled:pointer-events-none', className)}
            {...props}
        />
    );
});

export default Button;
